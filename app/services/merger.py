import os
import uuid
from pathlib import Path

from PyPDF2 import PdfWriter, PdfReader


class MergerService:
    @staticmethod
    def merge_pdfs(file_paths: list[Path], output_dir: Path) -> Path:
        writer = PdfWriter()
        for fp in file_paths:
            reader = PdfReader(str(fp))
            for page in reader.pages:
                writer.add_page(page)
        output_path = output_dir / f"merged_{uuid.uuid4().hex[:8]}.pdf"
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path

    @staticmethod
    def merge_by_folders(folder_groups: dict[str, list[Path]], output_dir: Path) -> list[Path]:
        results = []
        for folder_name, files in folder_groups.items():
            if not files:
                continue
            writer = PdfWriter()
            for fp in files:
                reader = PdfReader(str(fp))
                for page in reader.pages:
                    writer.add_page(page)
            safe_name = folder_name.replace(os.sep, "_").replace(":", "_")
            output_path = output_dir / f"{safe_name}_merged.pdf"
            with open(output_path, "wb") as f:
                writer.write(f)
            results.append(output_path)
        return results
