import io
import os
import shutil
import uuid
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count, get_context
from pathlib import Path

import fitz
import img2pdf
import numpy as np
import pikepdf
from PIL import Image

from app.config import COMPRESS_MAX_WORKERS
from app.services.errors import UserError
from app.services.pdf_utils import open_pdf, pixmap_to_image

# Niveis vao de 0 a 100. Sem rasterizar: 0 = so otimizacao sem perda ("Leve");
# acima disso as imagens embutidas sao recomprimidas, cada vez mais forte.
# O antigo "Normal" (JPEG 50, 2000 px) fica entre os niveis 60 e 70.
LEVEL_MIN, LEVEL_MAX = 0, 100
DEFAULT_LEVEL = 60
# Padroes do modo rasterizado ("Extremo"): reproduzem o perfil fixo antigo
# (150 dpi, JPEG ~15, fotos com ~600 px de largura).
DEFAULT_TEXT_LEVEL = 75
DEFAULT_IMAGE_LEVEL = 85

MIN_IMAGE_BYTES = 2000      # imagens menores que isso nao compensam recomprimir
TEXT_THRESHOLD = 180        # binarizacao das paginas de texto no modo rasterizado

# Valores antigos da API (antes da barra deslizante)
LEGACY_LEVELS = {
    "light": (0, False),
    "normal": (DEFAULT_LEVEL, False),
    "extreme": (DEFAULT_TEXT_LEVEL, True),
}

# Abaixo disso o custo de subir processos (spawn) supera o ganho
PARALLEL_MIN_PAGES = 8


def validate_level(value: int, name: str = "Nivel de compressao") -> int:
    if not LEVEL_MIN <= value <= LEVEL_MAX:
        raise UserError(f"{name} deve estar entre {LEVEL_MIN} e {LEVEL_MAX}")
    return value


def _lerp(start: float, end: float, level: int) -> int:
    return round(start + (end - start) * level / LEVEL_MAX)


def recompress_params(level: int) -> dict:
    """Parametros da recompressao de imagens embutidas (modo sem rasterizar)."""
    return {
        "quality": _lerp(85, 25, level),
        "max_dim": _lerp(4000, 1200, level),
    }


def raster_params(text_level: int, image_level: int) -> dict:
    """Parametros do modo rasterizado: texto e imagens sao controlados separadamente."""
    return {
        "dpi": _lerp(300, 100, text_level),
        "text_threshold": TEXT_THRESHOLD,
        "photo_quality": _lerp(60, 10, image_level),
        "photo_max_width": _lerp(1600, 400, image_level),
    }


def _is_page_color_or_photo(pil_image: Image.Image) -> bool:
    img = pil_image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    sat = 255 - arr.min(axis=2)
    mean_saturation = sat.mean()
    gray_arr = np.array(img.convert("L"), dtype=np.float64)
    return mean_saturation > 30 or gray_arr.var() > 2000


def _encode_page(page: Image.Image, profile: dict) -> bytes:
    buf = io.BytesIO()
    if _is_page_color_or_photo(page):
        w, h = page.size
        new_w = min(profile["photo_max_width"], w)
        new_h = max(1, int(h * new_w / w))
        page = page.resize((new_w, new_h), Image.LANCZOS)
        page.save(buf, format="JPEG", quality=profile["photo_quality"], optimize=True)
    else:
        threshold = profile["text_threshold"]
        bw = page.convert("L").point(lambda x: 255 if x > threshold else 0, mode="1")
        bw.save(buf, format="TIFF", compression="group4")
    return buf.getvalue()


def _process_pages(args) -> list[tuple[int, bytes, tuple[float, float]]]:
    """Renderiza e codifica um bloco de paginas. Roda em processo separado."""
    file_path, page_indices, profile = args
    results = []
    doc = fitz.open(file_path)
    try:
        for idx in page_indices:
            page = doc[idx]
            pix = page.get_pixmap(dpi=profile["dpi"], alpha=False)
            img = pixmap_to_image(pix)
            results.append((idx, _encode_page(img, profile), (page.rect.width, page.rect.height)))
    finally:
        doc.close()
    return results


class CompressorService:
    @staticmethod
    def compress_pdf(file_path: Path, output_dir: Path, level: int = DEFAULT_LEVEL,
                     extreme: bool = False, image_level: int = DEFAULT_IMAGE_LEVEL) -> Path:
        """level: forca da compressao (0-100). Com extreme=True as paginas sao rasterizadas;
        level controla o texto e image_level as paginas com fotos."""
        validate_level(level)
        validate_level(image_level, "Nivel de compressao das imagens")
        open_pdf(file_path).close()

        output_path = output_dir / f"{file_path.stem}_compressed.pdf"
        work_dir = output_dir / f"compress_{uuid.uuid4().hex[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            # "Leve" e sempre um candidato: o resultado nunca fica maior que ele
            candidates = [CompressorService._optimize(file_path, work_dir / "light.pdf")]
            if extreme:
                rasterized = CompressorService._rasterize(
                    file_path, work_dir / "raster.pdf", raster_params(level, image_level)
                )
                candidates.append(rasterized)
            elif level > LEVEL_MIN:
                recompressed = CompressorService._recompress_images(
                    file_path, work_dir / "images.pdf", recompress_params(level)
                )
                candidates.append(CompressorService._optimize(recompressed, work_dir / "images_opt.pdf"))

            best = min(candidates, key=os.path.getsize)
            shutil.move(str(best), str(output_path))
        finally:
            shutil.rmtree(str(work_dir), ignore_errors=True)
        return output_path

    @staticmethod
    def _optimize(src: Path, dest: Path) -> Path:
        """Otimizacao sem perda: remove recursos nao usados e recompacta streams.
        Se nao reduzir, mantem o arquivo de origem."""
        with pikepdf.Pdf.open(str(src)) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(
                str(dest),
                compress_streams=True,
                recompress_flate=True,
                linearize=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        if os.path.getsize(dest) >= os.path.getsize(src):
            shutil.copy2(str(src), str(dest))
        return dest

    @staticmethod
    def _recompress_images(file_path: Path, dest: Path, params: dict) -> Path:
        """Recomprime as imagens embutidas em JPEG; texto e vetores ficam intactos."""
        doc = fitz.open(str(file_path))
        seen_xrefs: set[int] = set()

        try:
            for page in doc:
                for img in page.get_images():
                    xref, smask = img[0], img[1]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                    # Imagens com mascara de transparencia perderiam o alpha ao virar JPEG
                    if smask:
                        continue

                    try:
                        img_data = doc.extract_image(xref)
                        size_in_pdf = img_data.get("size", 0)
                        if size_in_pdf < MIN_IMAGE_BYTES:
                            continue

                        pil_img = Image.open(io.BytesIO(img_data["image"]))
                        if pil_img.mode not in ("RGB", "L"):
                            pil_img = pil_img.convert("RGB")

                        max_dim = max(pil_img.size)
                        if max_dim > params["max_dim"]:
                            ratio = params["max_dim"] / max_dim
                            new_w = max(1, int(pil_img.width * ratio))
                            new_h = max(1, int(pil_img.height * ratio))
                            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=params["quality"], optimize=True)
                        new_bytes = buf.getvalue()

                        if len(new_bytes) < size_in_pdf * 0.9:
                            page.replace_image(xref, stream=new_bytes)
                    except Exception:
                        continue

            doc.ez_save(
                str(dest),
                garbage=4,
                deflate=True,
                deflate_images=True,
                use_objstms=1,
                compression_effort=1,
            )
        finally:
            doc.close()
        return dest

    @staticmethod
    def _rasterize(file_path: Path, dest: Path, profile: dict) -> Path:
        """Rasteriza cada pagina: texto vira preto e branco (CCITT G4), fotos viram JPEG."""
        doc = fitz.open(str(file_path))
        total = doc.page_count
        doc.close()

        indices = list(range(total))
        num_workers = min(COMPRESS_MAX_WORKERS, max(1, cpu_count() - 1))
        results: list[tuple[int, bytes, tuple[float, float]]] = []

        if total < PARALLEL_MIN_PAGES or num_workers == 1:
            results = _process_pages((str(file_path), indices, profile))
        else:
            chunk_size = -(-total // num_workers)
            chunks = [
                (str(file_path), indices[i:i + chunk_size], profile)
                for i in range(0, total, chunk_size)
            ]
            # spawn em vez de fork: o worker do uvicorn tem varias threads, e fork de
            # processo com threads pode herdar locks travados.
            with ProcessPoolExecutor(max_workers=len(chunks), mp_context=get_context("spawn")) as executor:
                for chunk_result in executor.map(_process_pages, chunks):
                    results.extend(chunk_result)

        results.sort(key=lambda r: r[0])
        page_sizes = iter([size for _, _, size in results])

        # img2pdf chama layout_fun uma vez por imagem, na ordem: usamos o tamanho
        # original de cada pagina em vez de deduzir pelo DPI gravado na imagem.
        def layout_fun(_w_px, _h_px, _dpi):
            w, h = next(page_sizes)
            return w, h, w, h

        pdf_bytes = img2pdf.convert([data for _, data, _ in results], layout_fun=layout_fun)
        with open(dest, "wb") as f:
            f.write(pdf_bytes)
        return dest
