import io
import os
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count

import numpy as np
import img2pdf
import pikepdf
import fitz
from pdf2image import convert_from_path
from PIL import Image


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


def _is_page_color_or_photo(pil_image: Image.Image) -> bool:
    img = pil_image.convert("RGB")
    arr = np.array(img, dtype=np.uint8)
    sat = 255 - arr.min(axis=2)
    mean_saturation = sat.mean()
    gray = img.convert("L")
    gray_arr = np.array(gray, dtype=np.float64)
    variance = gray_arr.var()
    return mean_saturation > 30 or variance > 2000


def _process_chunk(args) -> list[tuple[int, bytes]]:
    chunk_pages, profile, base_index = args
    results = []
    for i, page in enumerate(chunk_pages):
        if _is_page_color_or_photo(page):
            w, h = page.size
            new_w = min(profile["photo_max_width"], w)
            ratio = new_w / w
            new_h = int(h * ratio)
            page = page.resize((new_w, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            page.save(buf, format="JPEG", quality=profile["photo_quality"], optimize=True)
        else:
            gray = page.convert("L")
            bw = gray.point(
                lambda x: 255 if x > profile["text_threshold"] else 0, mode="1"
            )
            buf = io.BytesIO()
            bw.save(buf, format="TIFF", compression="group4")
        results.append((base_index + i, buf.getvalue()))
    return results


class CompressorService:
    @staticmethod
    def compress_pdf(file_path: Path, output_dir: Path, level: str = "normal") -> Path:
        base_name = file_path.stem
        input_size = os.path.getsize(file_path)

        if level == "light":
            return CompressorService._compress_light(file_path, output_dir, base_name)
        if level == "normal":
            return CompressorService._compress_normal(file_path, output_dir, base_name, input_size)
        if level == "extreme":
            profile = COMPRESSION_PROFILES["extreme"]
            return CompressorService._compress_extreme(file_path, output_dir, base_name, profile, input_size)
        return CompressorService._compress_normal(file_path, output_dir, base_name, input_size)

    @staticmethod
    def _compress_light(file_path: Path, output_dir: Path, base_name: str,
                         suffix: str = "_compressed_light") -> Path:
        output_path = output_dir / f"{base_name}{suffix}.pdf"
        pdf = pikepdf.Pdf.open(str(file_path))
        pdf.remove_unreferenced_resources()
        pdf.save(
            str(output_path),
            compress_streams=True,
            recompress_flate=True,
            linearize=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
        pdf.close()

        if os.path.getsize(output_path) >= os.path.getsize(file_path):
            shutil.copy2(str(file_path), str(output_path))
        return output_path

    @staticmethod
    def _compress_normal(file_path: Path, output_dir: Path, base_name: str,
                          input_size: int) -> Path:
        output_path = output_dir / f"{base_name}_compressed_normal.pdf"
        doc = fitz.open(str(file_path))
        seen_xrefs: set[int] = set()

        for page in doc:
            for img in page.get_images():
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    img_data = doc.extract_image(xref)
                    size_in_pdf = img_data.get("size", 0)
                    if size_in_pdf < 2000:
                        continue

                    raw = img_data["image"]
                    pil_img = Image.open(io.BytesIO(raw))
                    if pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")

                    max_dim = max(pil_img.size)
                    if max_dim > 2000:
                        ratio = 2000 / max_dim
                        new_w = max(1, int(pil_img.width * ratio))
                        new_h = max(1, int(pil_img.height * ratio))
                        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=50, optimize=True)
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
        doc.close()

        output_size = os.path.getsize(output_path)
        if output_size >= input_size:
            return CompressorService._compress_light(
                file_path, output_dir, base_name, suffix="_compressed_normal"
            )

        return output_path

    @staticmethod
    def _compress_extreme(file_path: Path, output_dir: Path, base_name: str,
                           profile: dict, input_size: int) -> Path:
        pages = convert_from_path(str(file_path), dpi=profile["dpi"])
        num_workers = max(1, cpu_count() - 1)
        chunk_size = max(1, len(pages) // num_workers)
        chunks = []
        for i in range(0, len(pages), chunk_size):
            chunks.append((pages[i : i + chunk_size], profile, i))

        results = {}
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for chunk_result in executor.map(_process_chunk, chunks):
                for idx, img_bytes in chunk_result:
                    results[idx] = img_bytes

        ordered_bytes = [results[i] for i in sorted(results)]
        pdf_bytes = img2pdf.convert(ordered_bytes)

        output_path = output_dir / f"{base_name}_compressed_extreme.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        if os.path.getsize(output_path) >= input_size:
            return CompressorService._compress_light(
                file_path, output_dir, base_name, suffix="_compressed_extreme"
            )

        return output_path
