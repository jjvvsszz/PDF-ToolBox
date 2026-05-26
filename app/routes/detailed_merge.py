import logging
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.config import UPLOADS_DIR, MAX_FILES
from app.services.detailed_merger import detailed_merger

logger = logging.getLogger("pdf_toolbox.detailed_merge")
router = APIRouter()


@router.post("/detailed-merge/create-session")
async def create_session():
    session_id = detailed_merger.create_session(UPLOADS_DIR)
    thumb_dir = UPLOADS_DIR / session_id / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return {"session_id": session_id}


@router.post("/detailed-merge/add-pdf")
async def add_pdf(session_id: str = Form(...), files: list[UploadFile] = File(...)):
    if not files:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)
    if len(files) > MAX_FILES:
        return JSONResponse({"error": f"Maximo de {MAX_FILES} arquivos permitidos"}, status_code=400)

    session_dir = UPLOADS_DIR / session_id
    thumb_dir = session_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    total_added = 0
    for f in files:
        fp = session_dir / f.filename
        with open(fp, "wb") as out:
            content = await f.read()
            out.write(content)
        total_added += detailed_merger.add_pdf(session_id, fp, thumb_dir, UPLOADS_DIR)

    pages = detailed_merger.get_pages(session_id, UPLOADS_DIR)
    return {"total_added": total_added, "total_pages": len(pages), "pages": pages}


@router.post("/detailed-merge/reorder")
async def reorder_page(session_id: str = Form(...), index: int = Form(...), direction: str = Form(...)):
    if direction == "up":
        ok = detailed_merger.move_page_up(session_id, index, UPLOADS_DIR)
    elif direction == "down":
        ok = detailed_merger.move_page_down(session_id, index, UPLOADS_DIR)
    else:
        return JSONResponse({"error": "Direcao invalida"}, status_code=400)
    pages = detailed_merger.get_pages(session_id, UPLOADS_DIR)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/delete")
async def delete_page(session_id: str = Form(...), index: int = Form(...)):
    ok = detailed_merger.remove_page(session_id, index, UPLOADS_DIR)
    pages = detailed_merger.get_pages(session_id, UPLOADS_DIR)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/clear")
async def clear_all(session_id: str = Form(...)):
    ok = detailed_merger.clear_all(session_id, UPLOADS_DIR)
    pages = detailed_merger.get_pages(session_id, UPLOADS_DIR)
    return {"success": ok, "pages": pages}


@router.post("/detailed-merge/save")
async def save_pdf(session_id: str = Form(...)):
    session_dir = UPLOADS_DIR / session_id
    output_path = detailed_merger.save_pdf(session_id, session_dir, UPLOADS_DIR)
    if output_path is None:
        return JSONResponse({"error": "Nenhuma pagina adicionada"}, status_code=400)

    return FileResponse(
        output_path,
        filename="detailed_merged.pdf",
        media_type="application/pdf",
    )


@router.get("/detailed-merge/thumbnail/{session_id}/{thumb_name}")
async def get_thumbnail(session_id: str, thumb_name: str):
    thumb_path = UPLOADS_DIR / session_id / "thumbs" / thumb_name
    if not thumb_path.exists():
        return JSONResponse({"error": "Thumbnail nao encontrada"}, status_code=404)
    return FileResponse(str(thumb_path), media_type="image/png")
