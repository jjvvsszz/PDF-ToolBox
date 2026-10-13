import logging

from fastapi import APIRouter, UploadFile, File, Form

from app.routes._common import download, run_job
from app.routes.thumbnails import thumbnail_response
from app.services.blank_remover import BlankRemoverService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.blank_remover")
router = APIRouter()


@router.post("/remove-blanks")
def remove_blanks(file: UploadFile = File(...), threshold: int = Form(95)):
    def job(session_dir):
        BlankRemoverService.validate_threshold(threshold)
        fp = save_upload(file, session_dir)
        output_path = BlankRemoverService.remove_blank_pages(fp, session_dir, threshold)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao remover paginas em branco", job)


@router.post("/remove-blanks/preview")
def preview_blanks(file: UploadFile = File(...), threshold: int = Form(95)):
    def job(session_dir):
        BlankRemoverService.validate_threshold(threshold)
        fp = save_upload(file, session_dir)
        pages = BlankRemoverService.preview(fp, session_dir, threshold)
        return {
            "total_pages": len(pages),
            "blank_count": sum(1 for p in pages if p["is_blank"]),
            "pages": pages,
        }

    return run_job(logger, "Erro ao gerar preview de paginas em branco", job, keep_dir=True)


@router.get("/remove-blanks/thumbnail/{session_dir}/{thumb_name}")
def get_blank_thumbnail(session_dir: str, thumb_name: str):
    return thumbnail_response(session_dir, thumb_name)
