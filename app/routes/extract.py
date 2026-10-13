import logging

from fastapi import APIRouter, UploadFile, File, Form

from app.routes._common import download, run_job
from app.routes.thumbnails import thumbnail_response
from app.services.pdf_utils import open_pdf, render_thumbnail
from app.services.splitter import SplitterService
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.extract")
router = APIRouter()


@router.post("/extract")
def extract_pages(file: UploadFile = File(...), pages: str = Form(...)):
    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_path = SplitterService.split_by_range(fp, pages, session_dir)
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao extrair paginas", job)


@router.post("/extract/preview")
def preview_extract(file: UploadFile = File(...), pages: str = Form(...)):
    def job(session_dir):
        fp = save_upload(file, session_dir)
        thumb_dir = session_dir / "thumbs"
        doc = open_pdf(fp)
        try:
            page_nums = SplitterService.parse_range(pages, doc.page_count)
            result_pages = [
                {
                    "page_number": n + 1,
                    "thumbnail": render_thumbnail(doc[n], thumb_dir),
                    "session_dir": session_dir.name,
                }
                for n in page_nums
            ]
        finally:
            doc.close()
        return {"total_selected": len(page_nums), "pages": result_pages}

    return run_job(logger, "Erro ao gerar preview de extracao", job, keep_dir=True)


@router.get("/extract/thumbnail/{session_dir}/{thumb_name}")
def get_extract_thumbnail(session_dir: str, thumb_name: str):
    return thumbnail_response(session_dir, thumb_name)
