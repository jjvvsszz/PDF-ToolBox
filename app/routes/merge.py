import logging
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from app.config import UPLOADS_DIR, MAX_FILES
from app.services.merger import MergerService

logger = logging.getLogger("pdf_toolbox.merge")
router = APIRouter()


@router.post("/merge")
async def merge_pdfs(files: list[UploadFile] = File(...)):
    if not files:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)
    if len(files) > MAX_FILES:
        return JSONResponse({"error": f"Maximo de {MAX_FILES} arquivos permitidos"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    try:
        for f in files:
            fp = session_dir / f.filename
            with open(fp, "wb") as out:
                content = await f.read()
                out.write(content)
            saved_paths.append(fp)

        output_path = MergerService.merge_pdfs(saved_paths, session_dir)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except Exception:
        logger.exception("Erro ao mesclar PDFs")
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": "Erro ao processar o arquivo"}, status_code=500)
