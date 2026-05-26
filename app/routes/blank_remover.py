import logging
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.config import UPLOADS_DIR
from app.services.blank_remover import BlankRemoverService

logger = logging.getLogger("pdf_toolbox.blank_remover")
router = APIRouter()


@router.post("/remove-blanks")
async def remove_blanks(file: UploadFile = File(...), threshold: int = Form(95)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_path = BlankRemoverService.remove_blank_pages(fp, session_dir, threshold)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except ValueError as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        logger.exception("Erro ao remover paginas em branco")
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": "Erro ao processar o arquivo"}, status_code=500)


@router.post("/remove-blanks/preview")
async def preview_blanks(file: UploadFile = File(...), threshold: int = Form(95)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        pages = BlankRemoverService.preview(fp, session_dir, threshold)

        blank_count = sum(1 for p in pages if p["is_blank"])
        return {
            "total_pages": len(pages),
            "blank_count": blank_count,
            "pages": pages,
        }
    except ValueError as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        logger.exception("Erro ao gerar preview de paginas em branco")
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": "Erro ao processar o arquivo"}, status_code=500)


@router.get("/remove-blanks/thumbnail/{session_dir}/{thumb_name}")
async def get_blank_thumbnail(session_dir: str, thumb_name: str):
    thumb_path = UPLOADS_DIR / session_dir / "thumbs" / thumb_name
    if not thumb_path.exists():
        return JSONResponse({"error": "Thumbnail nao encontrada"}, status_code=404)
    return FileResponse(str(thumb_path), media_type="image/png")
