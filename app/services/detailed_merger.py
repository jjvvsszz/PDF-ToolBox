import json
import logging
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import fitz

from app.services.cleanup import INTERACTIVE_SESSION_FILE
from app.services.errors import SessionNotFound, UserError
from app.services.pdf_utils import open_pdf, render_thumbnail, save_pdf
from app.services.storage import file_lock, is_valid_session_id, touch

logger = logging.getLogger("pdf_toolbox.detailed_merger")

THUMB_SCALE = 0.2
LOCK_FILE = ".session.lock"


class DetailedMergerService:
    """Estado da sessao fica em disco (session.json), protegido por lock de arquivo
    para funcionar com varios workers do uvicorn."""

    @staticmethod
    def _session_dir(session_id: str, uploads_dir: Path) -> Path:
        if not is_valid_session_id(session_id):
            raise SessionNotFound()
        return uploads_dir / session_id

    @contextmanager
    def _session(self, session_id: str, uploads_dir: Path, write: bool = False):
        session_dir = self._session_dir(session_id, uploads_dir)
        session_file = session_dir / INTERACTIVE_SESSION_FILE
        if not session_file.exists():
            raise SessionNotFound()
        with file_lock(session_dir / LOCK_FILE):
            try:
                session = json.loads(session_file.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                raise SessionNotFound()
            yield session
            if write:
                tmp = session_dir / f"{INTERACTIVE_SESSION_FILE}.{uuid.uuid4().hex[:8]}.tmp"
                tmp.write_text(json.dumps(session), encoding="utf-8")
                os.replace(tmp, session_file)
        touch(session_dir)

    def create_session(self, uploads_dir: Path) -> str:
        session_id = uuid.uuid4().hex
        session_dir = uploads_dir / session_id
        (session_dir / "thumbs").mkdir(parents=True, exist_ok=True)
        (session_dir / INTERACTIVE_SESSION_FILE).write_text(json.dumps({"pages": []}), encoding="utf-8")
        return session_id

    def session_dir(self, session_id: str, uploads_dir: Path) -> Path:
        session_dir = self._session_dir(session_id, uploads_dir)
        if not (session_dir / INTERACTIVE_SESSION_FILE).exists():
            raise SessionNotFound()
        return session_dir

    def add_pdf(self, session_id: str, file_path: Path, uploads_dir: Path) -> int:
        session_dir = self.session_dir(session_id, uploads_dir)
        thumb_dir = session_dir / "thumbs"

        # Renderiza fora do lock: pode demorar em PDFs grandes
        doc = open_pdf(file_path)
        new_pages = []
        try:
            for page_idx, page in enumerate(doc):
                new_pages.append({
                    "file": file_path.relative_to(session_dir).as_posix(),
                    "page_index": page_idx,
                    "thumbnail": render_thumbnail(page, thumb_dir, THUMB_SCALE),
                    "original_filename": file_path.name,
                })
        finally:
            doc.close()

        with self._session(session_id, uploads_dir, write=True) as session:
            session["pages"].extend(new_pages)
        return len(new_pages)

    def get_pages(self, session_id: str, uploads_dir: Path) -> list[dict]:
        with self._session(session_id, uploads_dir) as session:
            return self._public(session["pages"])

    @staticmethod
    def _public(pages: list[dict]) -> list[dict]:
        return [
            {"thumbnail": p["thumbnail"], "original_filename": p["original_filename"],
             "page_index": p["page_index"]}
            for p in pages
        ]

    def move_page(self, session_id: str, index: int, direction: str, uploads_dir: Path) -> tuple[bool, list[dict]]:
        offset = {"up": -1, "down": 1}.get(direction)
        if offset is None:
            raise UserError("Direcao invalida")
        with self._session(session_id, uploads_dir, write=True) as session:
            pages = session["pages"]
            target = index + offset
            ok = 0 <= index < len(pages) and 0 <= target < len(pages)
            if ok:
                pages[index], pages[target] = pages[target], pages[index]
            return ok, self._public(pages)

    def remove_page(self, session_id: str, index: int, uploads_dir: Path) -> tuple[bool, list[dict]]:
        with self._session(session_id, uploads_dir, write=True) as session:
            pages = session["pages"]
            ok = 0 <= index < len(pages)
            if ok:
                del pages[index]
            return ok, self._public(pages)

    def clear_all(self, session_id: str, uploads_dir: Path) -> tuple[bool, list[dict]]:
        with self._session(session_id, uploads_dir, write=True) as session:
            session["pages"] = []
            return True, []

    def save_pdf(self, session_id: str, uploads_dir: Path) -> Path | None:
        session_dir = self.session_dir(session_id, uploads_dir)
        with self._session(session_id, uploads_dir) as session:
            pages = list(session["pages"])
        if not pages:
            return None

        root = session_dir.resolve()
        writer = fitz.open()
        sources: dict[str, fitz.Document] = {}
        try:
            for info in pages:
                src_path = (session_dir / info["file"]).resolve()
                if root not in src_path.parents:
                    raise UserError("Sessao corrompida")
                key = str(src_path)
                if key not in sources:
                    sources[key] = open_pdf(src_path)
                idx = info["page_index"]
                writer.insert_pdf(sources[key], from_page=idx, to_page=idx)
            output_path = session_dir / f"detailed_merged_{uuid.uuid4().hex[:8]}.pdf"
            save_pdf(writer, output_path)
        finally:
            writer.close()
            for src in sources.values():
                src.close()
        return output_path


detailed_merger = DetailedMergerService()
