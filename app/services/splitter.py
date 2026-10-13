import re
from pathlib import Path

import fitz

from app.services.errors import UserError
from app.services.pdf_utils import open_pdf, save_pdf

_PART_RE = re.compile(r"(\d+)|(\d*)-(\d*)")


class SplitterService:
    @staticmethod
    def split_pdf(file_path: Path, output_dir: Path) -> list[Path]:
        src = open_pdf(file_path)
        base_name = file_path.stem
        output_paths = []
        try:
            for i in range(src.page_count):
                writer = fitz.open()
                writer.insert_pdf(src, from_page=i, to_page=i)
                out_path = output_dir / f"{base_name}_pag_{i + 1}.pdf"
                save_pdf(writer, out_path)
                writer.close()
                output_paths.append(out_path)
        finally:
            src.close()
        return output_paths

    @staticmethod
    def split_by_range(file_path: Path, page_range: str, output_dir: Path) -> Path:
        doc = open_pdf(file_path)
        try:
            pages_to_extract = SplitterService.parse_range(page_range, doc.page_count)
            doc.select(pages_to_extract)
            output_path = output_dir / f"{file_path.stem}_extracted.pdf"
            save_pdf(doc, output_path)
        finally:
            doc.close()
        return output_path

    @staticmethod
    def parse_range(range_str: str, total_pages: int) -> list[int]:
        """Converte "1-3,5,8-" em indices 0-based. Levanta UserError para entradas invalidas."""
        cleaned = (range_str or "").replace(" ", "")
        if not cleaned:
            raise UserError("Informe o intervalo de paginas")

        pages: set[int] = set()
        for part in cleaned.split(","):
            if not part:
                continue
            m = _PART_RE.fullmatch(part)
            if not m or part == "-":
                raise UserError(f"Intervalo invalido: '{part}'. Use o formato 1-3,5,8-")
            if m.group(1):
                start = end = int(m.group(1))
            else:
                start = int(m.group(2)) if m.group(2) else 1
                end = int(m.group(3)) if m.group(3) else total_pages
            if start < 1:
                raise UserError("A numeracao de paginas comeca em 1")
            if start > total_pages or end > total_pages:
                raise UserError(
                    f"O documento tem {total_pages} pagina(s); '{part}' esta fora do intervalo"
                )
            if start > end:
                raise UserError(f"Intervalo invertido: '{part}'")
            pages.update(range(start - 1, end))

        if not pages:
            raise UserError("Nenhuma pagina selecionada")
        return sorted(pages)
