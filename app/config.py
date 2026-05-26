import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WORKERS = int(os.getenv("WORKERS", "4"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_FILES = int(os.getenv("MAX_FILES", "50"))
CLEANUP_DELAY_MINUTES = int(os.getenv("CLEANUP_DELAY_MINUTES", "3"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")

UPLOADS_DIR = BASE_DIR / "uploads"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
