import uuid
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from app.services.converter import ConverterService

router = APIRouter()
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


@router.post("/pdf-to-images")
async def pdf_to_images(file: UploadFile = File(...), format: str = Form("png")):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_paths = ConverterService.pdf_to_images(fp, session_dir, format)

        if len(output_paths) == 1:
            return FileResponse(
                output_paths[0],
                filename=output_paths[0].name,
            )

        zip_path = session_dir / "imagens.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for p in output_paths:
                zf.write(str(p), p.name)

        return FileResponse(
            zip_path,
            filename="pdf_para_imagens.zip",
            media_type="application/zip",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/images-to-pdf")
async def images_to_pdf(files: list[UploadFile] = File(...)):
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

        output_path = ConverterService.images_to_pdf(saved_paths, session_dir)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/office-to-pdf")
async def office_to_pdf(file: UploadFile = File(...)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_path = ConverterService.office_to_pdf(fp, session_dir)

        if output_path is None:
            return JSONResponse(
                {"error": "LibreOffice não encontrado. Instale o LibreOffice no servidor."},
                status_code=500,
            )

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/pdf",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/pdf-to-office")
async def pdf_to_office(file: UploadFile = File(...)):
    if not file:
        return JSONResponse({"error": "Nenhum arquivo enviado"}, status_code=400)

    session_dir = UPLOADS_DIR / uuid.uuid4().hex
    session_dir.mkdir(parents=True, exist_ok=True)

    try:
        fp = session_dir / file.filename
        with open(fp, "wb") as out:
            content = await file.read()
            out.write(content)

        output_path = ConverterService.pdf_to_docx(fp, session_dir)

        return FileResponse(
            output_path,
            filename=output_path.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as e:
        shutil.rmtree(str(session_dir), ignore_errors=True)
        return JSONResponse({"error": str(e)}, status_code=500)
