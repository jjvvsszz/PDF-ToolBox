import logging

from fastapi import APIRouter, UploadFile, File, Form

from app.routes._common import download, run_job
from app.services.compressor import CompressorService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.compress")
router = APIRouter()


@router.post("/compress")
def compress_pdf(file: UploadFile = File(...), level: str = Form("normal")):
    if level not in ("light", "normal", "extreme"):
        level = "normal"

    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_path = CompressorService.compress_pdf(fp, session_dir, level=level)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao comprimir PDF", job)
