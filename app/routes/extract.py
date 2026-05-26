import logging
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import fitz
from PIL import Image

from app.config import UPLOADS_DIR
from app.services.splitter import SplitterService

logger = logging.getLogger("pdf_toolbox.extract")
router = APIRouter()


@router.post("/extract")
async def extract_pages(file: UploadFile = File(...), pages: str = Form(...)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)
    if not pages:
        return JSONResponse({"error": "Informe o intervalo de paginas"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_path = SplitterService.split_by_range(fp, pages, session_dir)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except ValueError as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        logger.exception("Erro ao extrair paginas")
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": "Erro ao processar o arquivo"}, status_code=500)


@router.post("/extract/preview")
async def preview_extract(file: UploadFile = File(...), pages: str = Form(...)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)
    if not pages:
        return JSONResponse({"error": "Informe o intervalo de paginas"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = session_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        doc = fitz.open(str(fp))
        total_pages = len(doc)
        page_nums = SplitterService.parse_range(pages, total_pages)

        result_pages = []
        for page_num in page_nums:
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            thumb_name = f"{uuid.uuid4().hex}.png"
            thumb_path = thumb_dir / thumb_name
            img.save(str(thumb_path), "PNG")
            result_pages.append({
                "page_number": page_num + 1,
                "thumbnail": thumb_name,
                "session_dir": session_dir.name,
            })

        doc.close()

        return {
            "total_selected": len(page_nums),
            "pages": result_pages,
        }
    except ValueError as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        logger.exception("Erro ao gerar preview de extracao")
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": "Erro ao processar o arquivo"}, status_code=500)


@router.get("/extract/thumbnail/{session_dir}/{thumb_name}")
async def get_extract_thumbnail(session_dir: str, thumb_name: str):
    thumb_path = UPLOADS_DIR / session_dir / "thumbs" / thumb_name
    if not thumb_path.exists():
        return JSONResponse({"error": "Thumbnail nao encontrada"}, status_code=404)
    return FileResponse(str(thumb_path), media_type="image/png")
