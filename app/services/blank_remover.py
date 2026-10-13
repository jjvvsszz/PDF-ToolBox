from pathlib import Path

import fitz
import numpy as np

from app.services.errors import UserError
from app.services.pdf_utils import open_pdf, save_pdf, save_thumbnail

MIN_THRESHOLD = 1
MAX_THRESHOLD = 99


class BlankRemoverService:
    RENDER_SCALE = 0.25
    GRAYSCALE_WEIGHTS = [0.2989, 0.5870, 0.1140]
    MIN_MEAN_BRIGHTNESS = 250

    @staticmethod
    def validate_threshold(threshold: int) -> int:
        if not MIN_THRESHOLD <= threshold <= MAX_THRESHOLD:
            raise UserError(
                f"Sensibilidade deve estar entre {MIN_THRESHOLD} e {MAX_THRESHOLD}"
            )
        return threshold

    @staticmethod
    def _max_std(threshold: int) -> float:
        return (100 - threshold) / 5.0 * 2.5

    @staticmethod
    def _render(page: fitz.Page) -> fitz.Pixmap:
        scale = BlankRemoverService.RENDER_SCALE
        return page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

    @staticmethod
    def _is_blank(pix: fitz.Pixmap, threshold: int) -> bool:
        samples = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        if pix.n >= 3:
            gray = np.dot(samples[..., :3], BlankRemoverService.GRAYSCALE_WEIGHTS)
        else:
            gray = samples
        return (
            gray.mean() >= BlankRemoverService.MIN_MEAN_BRIGHTNESS
            and gray.std() < BlankRemoverService._max_std(threshold)
        )

    @staticmethod
    def preview(file_path: Path, session_dir: Path, threshold: int) -> list[dict]:
        BlankRemoverService.validate_threshold(threshold)
        thumb_dir = session_dir / "thumbs"
        doc = open_pdf(file_path)
        pages = []
        try:
            for i, page in enumerate(doc):
                pix = BlankRemoverService._render(page)
                pages.append({
                    "page_number": i + 1,
                    "is_blank": bool(BlankRemoverService._is_blank(pix, threshold)),
                    "thumbnail": save_thumbnail(pix, thumb_dir),
                    "session_dir": session_dir.name,
                })
        finally:
            doc.close()
        return pages

    @staticmethod
    def remove_blank_pages(file_path: Path, output_dir: Path, threshold: int) -> Path:
        BlankRemoverService.validate_threshold(threshold)
        doc = open_pdf(file_path)
        try:
            keep = [
                i for i, page in enumerate(doc)
                if not BlankRemoverService._is_blank(BlankRemoverService._render(page), threshold)
            ]
            if not keep:
                raise UserError("Todas as paginas foram detectadas como brancas. Nenhuma pagina restaria.")
            if len(keep) == doc.page_count:
                raise UserError("Nenhuma pagina em branco detectada.")

            doc.select(keep)
            output_path = output_dir / f"{file_path.stem}_sem_brancos.pdf"
            save_pdf(doc, output_path)
        finally:
            doc.close()
        return output_path
