import io
import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from pathlib import Path

import fitz
import img2pdf
import numpy as np
import pikepdf
from PIL import Image

from app.services.pdf_utils import open_pdf, pixmap_to_image


COMPRESSION_PROFILES = {
    "light": {
        "label": "Leve",
        "desc": "Reducao sutil (~10-25%). Zero perda de qualidade — limpa metadados e recompacta streams internos.",
    },
    "normal": {
        "label": "Normal",
        "desc": "Reducao moderada (~40-60%). Recompressao de imagens embutidas. Texto e vetores intactos.",
        "photo_quality": 50,
        "max_dim": 2000,
        "min_image_bytes": 2000,
    },
    "extreme": {
        "label": "Extremo",
        "dpi": 150,
        "desc": "Maxima reducao (~70-95%). Rasteriza todas as paginas e aplica deteccao inteligente de fotos vs texto. Perda visual significativa — texto deixa de ser selecionavel.",
        "photo_quality": 15,
        "photo_max_width": 600,
        "text_threshold": 180,
    },
}

# Abaixo disso o custo de subir processos (spawn no Windows) supera o ganho
PARALLEL_MIN_PAGES = 8
MAX_PARALLEL_WORKERS = 4


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
    def compress_pdf(file_path: Path, output_dir: Path, level: str = "normal") -> Path:
        open_pdf(file_path).close()
        base_name = file_path.stem
        input_size = os.path.getsize(file_path)

        if level == "light":
            return CompressorService._compress_light(file_path, output_dir, base_name)
        if level == "extreme":
            profile = COMPRESSION_PROFILES["extreme"]
            return CompressorService._compress_extreme(file_path, output_dir, base_name, profile, input_size)
        return CompressorService._compress_normal(file_path, output_dir, base_name, input_size)

    @staticmethod
    def _compress_light(file_path: Path, output_dir: Path, base_name: str,
                        suffix: str = "_compressed_light") -> Path:
        output_path = output_dir / f"{base_name}{suffix}.pdf"
        with pikepdf.Pdf.open(str(file_path)) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(
                str(output_path),
                compress_streams=True,
                recompress_flate=True,
                linearize=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

        if os.path.getsize(output_path) >= os.path.getsize(file_path):
            shutil.copy2(str(file_path), str(output_path))
        return output_path

    @staticmethod
    def _compress_normal(file_path: Path, output_dir: Path, base_name: str,
                         input_size: int) -> Path:
        profile = COMPRESSION_PROFILES["normal"]
        output_path = output_dir / f"{base_name}_compressed_normal.pdf"
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
                        if size_in_pdf < profile["min_image_bytes"]:
                            continue

                        pil_img = Image.open(io.BytesIO(img_data["image"]))
                        if pil_img.mode not in ("RGB", "L"):
                            pil_img = pil_img.convert("RGB")

                        max_dim = max(pil_img.size)
                        if max_dim > profile["max_dim"]:
                            ratio = profile["max_dim"] / max_dim
                            new_w = max(1, int(pil_img.width * ratio))
                            new_h = max(1, int(pil_img.height * ratio))
                            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=profile["photo_quality"], optimize=True)
                        new_bytes = buf.getvalue()

                        if len(new_bytes) < size_in_pdf * 0.9:
                            page.replace_image(xref, stream=new_bytes)
                    except Exception:
                        continue

            doc.ez_save(
                str(output_path),
                garbage=4,
                deflate=True,
                deflate_images=True,
                use_objstms=1,
                compression_effort=1,
            )
        finally:
            doc.close()

        if os.path.getsize(output_path) >= input_size:
            return CompressorService._compress_light(
                file_path, output_dir, base_name, suffix="_compressed_normal"
            )
        return output_path

    @staticmethod
    def _compress_extreme(file_path: Path, output_dir: Path, base_name: str,
                          profile: dict, input_size: int) -> Path:
        doc = fitz.open(str(file_path))
        total = doc.page_count
        doc.close()

        indices = list(range(total))
        num_workers = min(MAX_PARALLEL_WORKERS, max(1, cpu_count() - 1))
        results: list[tuple[int, bytes, tuple[float, float]]] = []

        if total < PARALLEL_MIN_PAGES or num_workers == 1:
            results = _process_pages((str(file_path), indices, profile))
        else:
            chunk_size = -(-total // num_workers)
            chunks = [
                (str(file_path), indices[i:i + chunk_size], profile)
                for i in range(0, total, chunk_size)
            ]
            with ProcessPoolExecutor(max_workers=len(chunks)) as executor:
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

        output_path = output_dir / f"{base_name}_compressed_extreme.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        if os.path.getsize(output_path) >= input_size:
            return CompressorService._compress_light(
                file_path, output_dir, base_name, suffix="_compressed_extreme"
            )
        return output_path
