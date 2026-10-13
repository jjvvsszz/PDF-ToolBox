import gc
import uuid
from pathlib import Path

import fitz
from PIL import Image

from app.services.errors import UserError

THUMB_SCALE = 0.25


def open_pdf(file_path: Path) -> fitz.Document:
    """Abre um PDF validando formato, senha e quantidade de paginas."""
    name = file_path.name
    invalid = UserError(f"'{name}' nao e um PDF valido ou esta corrompido.")
    with open(file_path, "rb") as fh:
        if b"%PDF-" not in fh.read(1024):
            raise invalid
    try:
        doc = fitz.open(str(file_path), filetype="pdf")
    except Exception:
        doc = None
    if doc is None:
        # Se a abertura falha o MuPDF mantem o handle ate o GC (fora do except, para o
        # traceback nao segurar a referencia); no Windows isso impede apagar a sessao.
        gc.collect()
        raise invalid
    # O PyMuPDF abre imagens como documento mesmo com filetype="pdf"
    if not doc.is_pdf:
        doc.close()
        raise invalid
    if doc.needs_pass:
        doc.close()
        raise UserError(f"'{name}' esta protegido por senha. Remova a senha e tente novamente.")
    if doc.page_count == 0:
        doc.close()
        raise UserError(f"'{name}' nao possui paginas.")
    return doc


def validate_pdf(file_path: Path) -> int:
    doc = open_pdf(file_path)
    count = doc.page_count
    doc.close()
    return count


def pixmap_to_image(pix: fitz.Pixmap) -> Image.Image:
    mode = {1: "L", 3: "RGB", 4: "RGBA"}[pix.n]
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def save_thumbnail(pix: fitz.Pixmap, thumb_dir: Path) -> str:
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_name = f"{uuid.uuid4().hex}.png"
    pix.save(str(thumb_dir / thumb_name))
    return thumb_name


def render_thumbnail(page: fitz.Page, thumb_dir: Path, scale: float = THUMB_SCALE) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return save_thumbnail(pix, thumb_dir)


def save_pdf(doc: fitz.Document, output_path: Path):
    doc.save(str(output_path), garbage=3, deflate=True)
