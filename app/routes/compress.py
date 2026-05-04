import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.services.compressor import CompressorService

router = APIRouter()
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/compress")
async def compress_pdf(file: UploadFile = File(...), level: str = Form("normal")):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)
    if level not in ("light", "normal", "extreme"):
        level = "normal"

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_path = CompressorService.compress_pdf(fp, session_dir, level=level)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)
