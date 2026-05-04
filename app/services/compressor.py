import io
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count

import numpy as np
import img2pdf
from pdf2image import convert_from_path
from PIL import Image


COMPRESSION_PROFILES = {
    "light": {
        "label": "Leve",
        "dpi": 200,
        "smart_detect": False,
        "photo_quality": 75,
        "photo_max_width": 1800,
        "text_quality": 60,
        "text_threshold": None,
    },
    "normal": {
        "label": "Normal",
        "dpi": 170,
        "smart_detect": False,
        "photo_quality": 45,
        "photo_max_width": 1000,
        "text_quality": 35,
        "text_threshold": None,
    },
    "extreme": {
        "label": "Extremo",
        "dpi": 150,
        "smart_detect": True,
        "photo_quality": 15,
        "photo_max_width": 600,
        "text_quality": None,
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
    smart = profile["smart_detect"]
    for i, page in enumerate(chunk_pages):
        if smart and _is_page_color_or_photo(page):
            w, h = page.size
            new_w = min(profile["photo_max_width"], w)
            ratio = new_w / w
            new_h = int(h * ratio)
            page = page.resize((new_w, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            page.save(buf, format="JPEG", quality=profile["photo_quality"], optimize=True)
        elif smart:
            gray = page.convert("L")
            bw = gray.point(
                lambda x: 255 if x > profile["text_threshold"] else 0, mode="1"
            )
            buf = io.BytesIO()
            bw.save(buf, format="TIFF", compression="group4")
        else:
            w, h = page.size
            new_w = min(profile["photo_max_width"], w)
            ratio = new_w / w
            new_h = int(h * ratio)
            if new_w < w:
                page = page.resize((new_w, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            page.save(buf, format="JPEG", quality=profile["photo_quality"], optimize=True)
        results.append((base_index + i, buf.getvalue()))
    return results


class CompressorService:
    @staticmethod
    def compress_pdf(file_path: Path, output_dir: Path, level: str = "normal") -> Path:
        profile = COMPRESSION_PROFILES.get(level, COMPRESSION_PROFILES["normal"])
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

        base_name = file_path.stem
        suffix = f"_{level}" if level != "normal" else ""
        output_path = output_dir / f"{base_name}_compressed{suffix}.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path
