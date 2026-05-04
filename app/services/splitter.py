import os
import uuid
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter


class SplitterService:
    @staticmethod
    def split_pdf(file_path: Path, output_dir: Path) -> list[Path]:
        reader = PdfReader(str(file_path))
        base_name = file_path.stem
        output_paths = []
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            out_path = output_dir / f"{base_name}_pag_{i + 1}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            output_paths.append(out_path)
        return output_paths

    @staticmethod
    def split_by_range(file_path: Path, page_range: str, output_dir: Path) -> Path:
        reader = PdfReader(str(file_path))
        total = len(reader.pages)
        pages_to_extract = SplitterService._parse_range(page_range, total)

        writer = PdfWriter()
        for page_num in pages_to_extract:
            writer.add_page(reader.pages[page_num])

        base_name = file_path.stem
        output_path = output_dir / f"{base_name}_extracted.pdf"
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path

    @staticmethod
    def parse_range(range_str: str, total_pages: int) -> list[int]:
        return SplitterService._parse_range(range_str, total_pages)

    @staticmethod
    def _parse_range(range_str: str, total_pages: int) -> list[int]:
        pages = set()
        parts = range_str.replace(" ", "").split(",")
        for part in parts:
            if "-" in part:
                start, end = part.split("-", 1)
                start = int(start) - 1 if start else 0
                end = int(end) - 1 if end else total_pages - 1
                for p in range(max(0, start), min(total_pages, end + 1)):
                    pages.add(p)
            else:
                p = int(part) - 1
                if 0 <= p < total_pages:
                    pages.add(p)
        return sorted(pages)
