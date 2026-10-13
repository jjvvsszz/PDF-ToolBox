import logging
import zipfile

from fastapi import APIRouter, UploadFile, File

from app.routes._common import download, run_job
from app.services.splitter import SplitterService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.split")
router = APIRouter()


@router.post("/split")
def split_pdf(file: UploadFile = File(...)):
    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_paths = SplitterService.split_pdf(fp, session_dir)

        if len(output_paths) == 1:
            return download(output_paths[0], session_dir, "application/pdf")

        zip_path = session_dir / "split_pages.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for p in output_paths:
                zf.write(str(p), p.name)
        return download(zip_path, session_dir, "application/zip", filename="paginas_separadas.zip")

    return run_job(logger, "Erro ao dividir PDF", job)
