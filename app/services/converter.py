import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pdf2docx import Converter as Pdf2DocxConverter

from app.config import OFFICE_TIMEOUT_SECONDS
from app.services.errors import UserError
from app.services.pdf_utils import open_pdf, pixmap_to_image

logger = logging.getLogger("pdf_toolbox.converter")

# formato pedido -> (formato do Pillow, extensao, media type)
IMAGE_FORMATS = {
    "png": ("PNG", "png", "image/png"),
    "jpg": ("JPEG", "jpg", "image/jpeg"),
    "jpeg": ("JPEG", "jpg", "image/jpeg"),
}

OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}


class ConverterService:
    @staticmethod
    def image_format(fmt: str) -> tuple[str, str, str]:
        spec = IMAGE_FORMATS.get((fmt or "").lower())
        if spec is None:
            raise UserError("Formato de imagem invalido. Use PNG ou JPG.")
        return spec

    @staticmethod
    def pdf_to_images(file_path: Path, output_dir: Path, fmt: str = "png", dpi: int = 200) -> list[Path]:
        pil_format, ext, _ = ConverterService.image_format(fmt)
        doc = open_pdf(file_path)
        output_paths = []
        try:
            for i, page in enumerate(doc):
                img = pixmap_to_image(page.get_pixmap(dpi=dpi, alpha=False))
                out_path = output_dir / f"{file_path.stem}_pag_{i + 1}.{ext}"
                save_kwargs = {"quality": 90} if pil_format == "JPEG" else {}
                img.save(str(out_path), pil_format, dpi=(dpi, dpi), **save_kwargs)
                output_paths.append(out_path)
        finally:
            doc.close()
        return output_paths

    @staticmethod
    def _load_image(img_path: Path) -> Image.Image:
        try:
            with Image.open(str(img_path)) as src:
                img = ImageOps.exif_transpose(src)
                img.load()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
            raise UserError(f"'{img_path.name}' nao e uma imagem valida ou e grande demais.")

        has_alpha = img.mode in ("RGBA", "LA", "PA") or (
            img.mode == "P" and "transparency" in img.info
        )
        if has_alpha:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            img = background
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return img

    @staticmethod
    def images_to_pdf(image_paths: list[Path], output_dir: Path) -> Path:
        if not image_paths:
            raise UserError("Nenhuma imagem enviada")
        images = []
        try:
            for img_path in image_paths:
                images.append(ConverterService._load_image(img_path))
            output_path = output_dir / f"images_to_pdf_{uuid.uuid4().hex[:8]}.pdf"
            images[0].save(
                str(output_path),
                "PDF",
                save_all=True,
                append_images=images[1:],
                resolution=100.0,
            )
        finally:
            for img in images:
                img.close()
        return output_path

    @staticmethod
    def office_to_pdf(file_path: Path, output_dir: Path) -> Path:
        if file_path.suffix.lower() not in OFFICE_EXTENSIONS:
            raise UserError("Formato nao suportado. Envie um arquivo do Word, Excel, PowerPoint ou OpenDocument.")

        soffice = ConverterService._find_soffice()
        if soffice is None:
            raise UserError("LibreOffice nao encontrado. Instale o LibreOffice no servidor.", status_code=503)

        work_dir = output_dir / f"office_conv_{uuid.uuid4().hex[:8]}"
        # Perfil proprio por conversao: instancias simultaneas do soffice com o mesmo
        # perfil falham silenciosamente.
        profile_dir = work_dir / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = work_dir / file_path.name
        shutil.copy2(str(file_path), str(tmp_file))
        try:
            try:
                result = subprocess.run(
                    [
                        soffice,
                        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                        "--headless", "--norestore",
                        "--convert-to", "pdf",
                        "--outdir", str(work_dir),
                        str(tmp_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=OFFICE_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                raise UserError("A conversao demorou demais e foi cancelada.", status_code=504)

            pdf_path = work_dir / f"{tmp_file.stem}.pdf"
            if not pdf_path.exists():
                logger.warning(
                    "LibreOffice nao gerou PDF (rc=%s): %s %s",
                    result.returncode, result.stdout.strip(), result.stderr.strip(),
                )
                raise UserError(
                    "Nao foi possivel converter o documento. Verifique se o arquivo nao esta "
                    "corrompido ou protegido por senha.",
                    status_code=422,
                )
            final_path = output_dir / f"{file_path.stem}_converted.pdf"
            shutil.move(str(pdf_path), str(final_path))
            return final_path
        finally:
            shutil.rmtree(str(work_dir), ignore_errors=True)

    @staticmethod
    def pdf_to_docx(file_path: Path, output_dir: Path) -> Path:
        open_pdf(file_path).close()
        output_path = output_dir / f"{file_path.stem}_converted.docx"
        cv = Pdf2DocxConverter(str(file_path))
        try:
            cv.convert(str(output_path))
        finally:
            cv.close()
        return output_path

    @staticmethod
    def _find_soffice() -> str | None:
        for name in ("soffice", "libreoffice"):
            found = shutil.which(name)
            if found:
                return found
        candidates = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "LibreOffice", "program", "soffice.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "LibreOffice", "program", "soffice.exe"),
            "/usr/bin/soffice",
            "/usr/local/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return None
