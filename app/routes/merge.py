import logging

from fastapi import APIRouter, UploadFile, File

from app.routes._common import download, run_job, too_many_files
from app.services.merger import MergerService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.merge")
router = APIRouter()


@router.post("/merge")
def merge_pdfs(files: list[UploadFile] = File(...)):
    if (err := too_many_files(files)) is not None:
        return err

    def job(session_dir):
        saved_paths = [save_upload(f, session_dir) for f in files]
        output_path = MergerService.merge_pdfs(saved_paths, session_dir)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao mesclar PDFs", job)
