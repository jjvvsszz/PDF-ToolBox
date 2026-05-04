import uuid
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import fitz


class DetailedMergerService:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        self._sessions[session_id] = {
            "pages": [],
        }
        return session_id

    def add_pdf(self, session_id: str, file_path: Path, thumb_dir: Path) -> int:
        session = self._sessions.get(session_id)
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
        return added

    def get_pages(self, session_id: str) -> list[dict]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return session["pages"]

    def move_page_up(self, session_id: str, index: int) -> bool:
        session = self._sessions.get(session_id)
        if session is None or index <= 0 or index >= len(session["pages"]):
            return False
        session["pages"][index], session["pages"][index - 1] = session["pages"][index - 1], session["pages"][index]
        return True

    def move_page_down(self, session_id: str, index: int) -> bool:
        session = self._sessions.get(session_id)
        if session is None or index < 0 or index >= len(session["pages"]) - 1:
            return False
        session["pages"][index], session["pages"][index + 1] = session["pages"][index + 1], session["pages"][index]
        return True

    def remove_page(self, session_id: str, index: int) -> bool:
        session = self._sessions.get(session_id)
        if session is None or index < 0 or index >= len(session["pages"]):
            return False
        del session["pages"][index]
        return True

    def clear_all(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session["pages"] = []
        return True

    def save_pdf(self, session_id: str, output_dir: Path) -> Path | None:
        session = self._sessions.get(session_id)
        if session is None or not session["pages"]:
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
        self._sessions.pop(session_id, None)


detailed_merger = DetailedMergerService()
