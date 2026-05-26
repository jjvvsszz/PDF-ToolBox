import json
import logging
import threading
import uuid
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import fitz

logger = logging.getLogger("pdf_toolbox.detailed_merger")


class DetailedMergerService:
    def __init__(self):
        self._locks: dict[str, threading.Lock] = {}

    def _get_lock(self, session_id: str) -> threading.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = threading.Lock()
        return self._locks[session_id]

    def _cleanup_lock(self, session_id: str):
        self._locks.pop(session_id, None)

    def _session_path(self, session_id: str, uploads_dir: Path) -> Path:
        return uploads_dir / session_id / "session.json"

    def _load_session(self, session_id: str, uploads_dir: Path) -> dict | None:
        path = self._session_path(session_id, uploads_dir)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_session(self, session_id: str, uploads_dir: Path, session: dict):
        path = self._session_path(session_id, uploads_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session), encoding="utf-8")

    def create_session(self, uploads_dir: Path) -> str:
        session_id = uuid.uuid4().hex
        session = {"pages": []}
        self._save_session(session_id, uploads_dir, session)
        return session_id

    def add_pdf(self, session_id: str, file_path: Path, thumb_dir: Path, uploads_dir: Path) -> int:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None:
                return 0
            doc = fitz.open(str(file_path))
            added = 0
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(0.2, 0.2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                thumb_name = f"{uuid.uuid4().hex}.png"
                thumb_path = thumb_dir / thumb_name
                img.save(str(thumb_path), "PNG")
                session["pages"].append({
                    "file_path": str(file_path),
                    "page_index": page_idx,
                    "thumbnail": thumb_name,
                    "original_filename": file_path.name,
                })
                added += 1
            doc.close()
            self._save_session(session_id, uploads_dir, session)
            return added

    def get_pages(self, session_id: str, uploads_dir: Path) -> list[dict]:
        session = self._load_session(session_id, uploads_dir)
        if session is None:
            return []
        return session.get("pages", [])

    def move_page_up(self, session_id: str, index: int, uploads_dir: Path) -> bool:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None or index <= 0 or index >= len(session["pages"]):
                return False
            session["pages"][index], session["pages"][index - 1] = session["pages"][index - 1], session["pages"][index]
            self._save_session(session_id, uploads_dir, session)
            return True

    def move_page_down(self, session_id: str, index: int, uploads_dir: Path) -> bool:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None or index < 0 or index >= len(session["pages"]) - 1:
                return False
            session["pages"][index], session["pages"][index + 1] = session["pages"][index + 1], session["pages"][index]
            self._save_session(session_id, uploads_dir, session)
            return True

    def remove_page(self, session_id: str, index: int, uploads_dir: Path) -> bool:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None or index < 0 or index >= len(session["pages"]):
                return False
            del session["pages"][index]
            self._save_session(session_id, uploads_dir, session)
            return True

    def clear_all(self, session_id: str, uploads_dir: Path) -> bool:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None:
                return False
            session["pages"] = []
            self._save_session(session_id, uploads_dir, session)
            return True

    def save_pdf(self, session_id: str, output_dir: Path, uploads_dir: Path) -> Path | None:
        lock = self._get_lock(session_id)
        with lock:
            session = self._load_session(session_id, uploads_dir)
            if session is None or not session.get("pages"):
                return None
            writer = PdfWriter()
            file_cache = {}
            for page_info in session["pages"]:
                fp = page_info["file_path"]
                if fp not in file_cache:
                    file_cache[fp] = PdfReader(fp)
                reader = file_cache[fp]
                writer.add_page(reader.pages[page_info["page_index"]])
            output_path = output_dir / f"detailed_merged_{uuid.uuid4().hex[:8]}.pdf"
            with open(output_path, "wb") as f:
                writer.write(f)
            return output_path

    def delete_session(self, session_id: str):
        self._cleanup_lock(session_id)


detailed_merger = DetailedMergerService()
