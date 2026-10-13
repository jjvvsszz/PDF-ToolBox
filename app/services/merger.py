import uuid
from pathlib import Path

import fitz

from app.services.pdf_utils import open_pdf, save_pdf


class MergerService:
    @staticmethod
    def merge_pdfs(file_paths: list[Path], output_dir: Path) -> Path:
        writer = fitz.open()
        try:
            for fp in file_paths:
                src = open_pdf(fp)
                try:
                    writer.insert_pdf(src)
                finally:
                    src.close()
            output_path = output_dir / f"merged_{uuid.uuid4().hex[:8]}.pdf"
            save_pdf(writer, output_path)
        finally:
            writer.close()
        return output_path
