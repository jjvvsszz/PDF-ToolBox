import logging
import zipfile

from fastapi import APIRouter, UploadFile, File, Form

from app.routes._common import download, run_job, too_many_files
from app.services.converter import ConverterService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.convert")
router = APIRouter()

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/pdf-to-images")
def pdf_to_images(file: UploadFile = File(...), format: str = Form("png")):
    def job(session_dir):
        _, _, media_type = ConverterService.image_format(format)
        fp = save_upload(file, session_dir)
        output_paths = ConverterService.pdf_to_images(fp, session_dir, format)

        if len(output_paths) == 1:
            return download(output_paths[0], session_dir, media_type)

        zip_path = session_dir / "imagens.zip"
        # Imagens ja sao comprimidas; ZIP_STORED evita gastar CPU a toa
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_STORED) as zf:
            for p in output_paths:
                zf.write(str(p), p.name)
        return download(zip_path, session_dir, "application/zip", filename="pdf_para_imagens.zip")

    return run_job(logger, "Erro ao converter PDF para imagens", job)


@router.post("/images-to-pdf")
def images_to_pdf(files: list[UploadFile] = File(...)):
    if (err := too_many_files(files)) is not None:
        return err

    def job(session_dir):
        saved_paths = [save_upload(f, session_dir) for f in files]
        output_path = ConverterService.images_to_pdf(saved_paths, session_dir)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao converter imagens para PDF", job)


@router.post("/office-to-pdf")
def office_to_pdf(file: UploadFile = File(...)):
    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_path = ConverterService.office_to_pdf(fp, session_dir)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao converter Office para PDF", job)


@router.post("/pdf-to-office")
def pdf_to_office(file: UploadFile = File(...)):
    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_path = ConverterService.pdf_to_docx(fp, session_dir)
        return download(output_path, session_dir, DOCX_MEDIA_TYPE)

    return run_job(logger, "Erro ao converter PDF para DOCX", job)
