import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from app.services.splitter import SplitterService

router = APIRouter()
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/split")
async def split_pdf(file: UploadFile = File(...)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_paths = SplitterService.split_pdf(fp, session_dir)

        if len(output_paths) == 1:
            return FileResponse(
                output_paths[0],
                filename=output_paths[0].name,
                media_type="application/pdf",
            )

        import zipfile
        zip_path = session_dir / "split_pages.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for p in output_paths:
                zf.write(str(p), p.name)

        return FileResponse(
            zip_path,
            filename="paginas_separadas.zip",
            media_type="application/zip",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)
