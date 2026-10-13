import logging

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.config import UPLOADS_DIR
from app.routes._common import GENERIC_ERROR, error, too_many_files
from app.routes.thumbnails import thumbnail_response
from app.services.detailed_merger import detailed_merger
from app.services.errors import SessionNotFound, UserError
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.detailed_merge")
router = APIRouter()


def _session_error(e: UserError):
    resp = error(e.message, e.status_code)
    if isinstance(e, SessionNotFound):
        resp.headers["X-Session-Expired"] = "1"
    return resp


@router.post("/detailed-merge/create-session")
def create_session():
    return {"session_id": detailed_merger.create_session(UPLOADS_DIR)}


@router.post("/detailed-merge/add-pdf")
def add_pdf(session_id: str = Form(...), files: list[UploadFile] = File(...)):
    if (err := too_many_files(files)) is not None:
        return err

    try:
        session_dir = detailed_merger.session_dir(session_id, UPLOADS_DIR)
        total_added = 0
        rejected = []
        for f in files:
            fp = save_upload(f, session_dir)
            try:
                total_added += detailed_merger.add_pdf(session_id, fp, UPLOADS_DIR)
            except SessionNotFound:
                raise
            except UserError as e:
                fp.unlink(missing_ok=True)
                rejected.append(e.message)
        pages = detailed_merger.get_pages(session_id, UPLOADS_DIR)
    except UserError as e:
        return _session_error(e)
    except Exception:
        logger.exception("Erro ao adicionar PDFs na mesclagem detalhada")
        return error(GENERIC_ERROR, 500)

    return {"total_added": total_added, "total_pages": len(pages), "pages": pages, "errors": rejected}


@router.post("/detailed-merge/reorder")
def reorder_page(session_id: str = Form(...), index: int = Form(...), direction: str = Form(...)):
    try:
        ok, pages = detailed_merger.move_page(session_id, index, direction, UPLOADS_DIR)
    except UserError as e:
        return _session_error(e)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/delete")
def delete_page(session_id: str = Form(...), index: int = Form(...)):
    try:
        ok, pages = detailed_merger.remove_page(session_id, index, UPLOADS_DIR)
    except UserError as e:
        return _session_error(e)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/clear")
def clear_all(session_id: str = Form(...)):
    try:
        ok, pages = detailed_merger.clear_all(session_id, UPLOADS_DIR)
    except UserError as e:
        return _session_error(e)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/save")
def save_pdf(session_id: str = Form(...)):
    try:
        output_path = detailed_merger.save_pdf(session_id, UPLOADS_DIR)
    except UserError as e:
        return _session_error(e)
    except Exception:
        logger.exception("Erro ao gerar PDF da mesclagem detalhada")
        return error(GENERIC_ERROR, 500)
    if output_path is None:
        return error("Nenhuma pagina adicionada")

    # A sessao continua ativa (o usuario pode seguir editando); so o PDF gerado e apagado
    return FileResponse(
        output_path,
        filename="detailed_merged.pdf",
        media_type="application/pdf",
        background=BackgroundTask(output_path.unlink, missing_ok=True),
    )


@router.get("/detailed-merge/thumbnail/{session_id}/{thumb_name}")
def get_thumbnail(session_id: str, thumb_name: str):
    return thumbnail_response(session_id, thumb_name)
