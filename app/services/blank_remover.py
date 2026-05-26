import uuid
from pathlib import Path

import fitz
import numpy as np
from PyPDF2 import PdfWriter, PdfReader
from PIL import Image


class BlankRemoverService:
    RENDER_SCALE = 0.25
    GRAYSCALE_WEIGHTS = [0.2989, 0.5870, 0.1140]
    MIN_MEAN_BRIGHTNESS = 250

    @staticmethod
    def _max_std(threshold: int) -> float:
        return (100 - threshold) / 5.0 * 2.5

    @staticmethod
    def _is_page_blank(page: fitz.Page, threshold: int) -> bool:
        pix = page.get_pixmap(
            matrix=fitz.Matrix(BlankRemoverService.RENDER_SCALE, BlankRemoverService.RENDER_SCALE)
        )
        samples = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )

        if pix.n >= 3:
            gray = np.dot(samples[..., :3], BlankRemoverService.GRAYSCALE_WEIGHTS)
        else:
            gray = samples

        mean_val = gray.mean()
        std_val = gray.std()

        return mean_val >= BlankRemoverService.MIN_MEAN_BRIGHTNESS and std_val < BlankRemoverService._max_std(threshold)

    @staticmethod
    def _generate_thumbnail(page: fitz.Page, thumb_dir: Path) -> str:
        pix = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        thumb_name = f"{uuid.uuid4().hex}.png"
        thumb_path = thumb_dir / thumb_name
        img.save(str(thumb_path), "PNG")
        return thumb_name

    @staticmethod
    def preview(file_path: Path, session_dir: Path, threshold: int) -> list[dict]:
        thumb_dir = session_dir / "thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(file_path))
        pages = []

        for i in range(len(doc)):
            page = doc[i]
            is_blank = BlankRemoverService._is_page_blank(page, threshold)
            thumb_name = BlankRemoverService._generate_thumbnail(page, thumb_dir)
            pages.append({
                "page_number": i + 1,
                "is_blank": bool(is_blank),
                "thumbnail": thumb_name,
                "session_dir": session_dir.name,
            })

        doc.close()
        return pages

    @staticmethod
    def remove_blank_pages(file_path: Path, output_dir: Path, threshold: int) -> Path:
        doc = fitz.open(str(file_path))
        blank_indices: set[int] = set()
        total_pages = len(doc)

        for i in range(total_pages):
            if BlankRemoverService._is_page_blank(doc[i], threshold):
                blank_indices.add(i)

        doc.close()

        if total_pages > 0 and len(blank_indices) == total_pages:
            raise ValueError("Todas as paginas foram detectadas como brancas. Nenhuma pagina restaria.")

        if not blank_indices:
            raise ValueError("Nenhuma pagina em branco detectada.")

        reader = PdfReader(str(file_path))
        writer = PdfWriter()

        for i in range(len(reader.pages)):
            if i not in blank_indices:
                writer.add_page(reader.pages[i])

        output_path = output_dir / f"{file_path.stem}_sem_brancos.pdf"
        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path
