import os
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.services.merger import MergerService

router = APIRouter()
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/merge")
async def merge_pdfs(files: list[UploadFile] = File(...)):
    if not files:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

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
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)
