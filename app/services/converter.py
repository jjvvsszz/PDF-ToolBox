import os
import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image
from pdf2image import convert_from_path
from pdf2docx import Converter as Pdf2DocxConverter


class ConverterService:
    @staticmethod
    def pdf_to_images(file_path: Path, output_dir: Path, format: str = "png", dpi: int = 200) -> list[Path]:
        pages = convert_from_path(str(file_path), dpi=dpi)
        output_paths = []
        base_name = file_path.stem
        for i, page in enumerate(pages):
            out_name = f"{base_name}_pag_{i + 1}.{format}"
            out_path = output_dir / out_name
            page.save(str(out_path), format.upper())
            output_paths.append(out_path)
        return output_paths

    @staticmethod
    def images_to_pdf(image_paths: list[Path], output_dir: Path) -> Path:
        images = []
        for img_path in image_paths:
            img = Image.open(str(img_path))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            images.append(img)

        output_path = output_dir / f"images_to_pdf_{uuid.uuid4().hex[:8]}.pdf"
        if images:
            images[0].save(
                str(output_path),
                "PDF",
                save_all=True,
                append_images=images[1:],
                resolution=100.0,
            )
        return output_path

    @staticmethod
    def office_to_pdf(file_path: Path, output_dir: Path) -> Path | None:
        soffice = ConverterService._find_soffice()
        if soffice is None:
            return None
        work_dir = output_dir / f"office_conv_{uuid.uuid4().hex[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = work_dir / file_path.name
        shutil.copy2(str(file_path), str(tmp_file))
        try:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(work_dir), str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            pdf_name = tmp_file.stem + ".pdf"
            pdf_path = work_dir / pdf_name
            if pdf_path.exists():
                final_path = output_dir / f"{file_path.stem}_converted.pdf"
                shutil.move(str(pdf_path), str(final_path))
                shutil.rmtree(str(work_dir), ignore_errors=True)
                return final_path
        except (subprocess.TimeoutExpired, Exception):
            pass
        shutil.rmtree(str(work_dir), ignore_errors=True)
        return None

    @staticmethod
    def pdf_to_docx(file_path: Path, output_dir: Path) -> Path:
        output_path = output_dir / f"{file_path.stem}_converted.docx"
        cv = Pdf2DocxConverter(str(file_path))
        cv.convert(str(output_path))
        cv.close()
        return output_path

    @staticmethod
    def _find_soffice() -> str | None:
        candidates = [
            "soffice",
            "soffice.exe",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "/usr/bin/soffice",
            "/usr/local/bin/soffice",
        ]
        for candidate in candidates:
            if shutil.which(candidate) or os.path.exists(candidate):
                return candidate
        return shutil.which("soffice") or shutil.which("libreoffice")
