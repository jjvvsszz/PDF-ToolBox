import logging

from fastapi import APIRouter, UploadFile, File, Form

from app.routes._common import download, error, run_job
from app.services.compressor import (
    DEFAULT_IMAGE_LEVEL,
    DEFAULT_LEVEL,
    LEGACY_LEVELS,
    CompressorService,
    validate_level,
)
from app.services.errors import UserError
from app.services.storage import save_upload

logger = logging.getLogger("pdf_toolbox.compress")
router = APIRouter()

TRUTHY = {"1", "true", "on", "yes", "sim"}


def _parse_level(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise UserError(f"{name} invalido: '{raw}'")
    return validate_level(value, name)


@router.post("/compress")
def compress_pdf(
    file: UploadFile = File(...),
    level: str = Form(str(DEFAULT_LEVEL)),
    extreme: str = Form("false"),
    image_level: str = Form(str(DEFAULT_IMAGE_LEVEL)),
):
    """level: 0 (sem perda) a 100. extreme=true rasteriza as paginas; nesse modo
    level controla o texto e image_level as paginas com fotos.
    Aceita tambem os valores antigos level=light|normal|extreme."""
    try:
        if level in LEGACY_LEVELS:
            level_value, is_extreme = LEGACY_LEVELS[level]
        else:
            level_value = _parse_level(level, "Nivel de compressao")
            is_extreme = extreme.strip().lower() in TRUTHY
        image_value = _parse_level(image_level, "Nivel de compressao das imagens")
    except UserError as e:
        return error(e.message, e.status_code)

    def job(session_dir):
        fp = save_upload(file, session_dir)
        output_path = CompressorService.compress_pdf(
            fp, session_dir, level=level_value, extreme=is_extreme, image_level=image_value
        )
        return download(output_path, session_dir, "application/pdf")

    return run_job(logger, "Erro ao comprimir PDF", job)
