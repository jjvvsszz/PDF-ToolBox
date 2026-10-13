import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    UPLOADS_DIR,
    STATIC_DIR,
    MAX_UPLOAD_SIZE_MB,
    CLEANUP_DELAY_MINUTES,
    CLEANUP_INTERVAL_SECONDS,
    SESSION_IDLE_MINUTES,
    BUSY_TIMEOUT_MINUTES,
    CORS_ORIGINS,
    LOG_LEVEL,
)
from app.middleware import BodySizeLimitMiddleware, CSRFMiddleware
from app.services.cleanup import cleanup_loop, cleanup_expired
from app.routes import pages, merge, split, compress, extract, convert, detailed_merge, blank_remover

VERSION = "2.0.0"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pdf_toolbox")


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    # Com varios workers, cada um executa isto: so remove o que ja expirou,
    # para nao apagar sessoes ativas de outro worker.
    removed = cleanup_expired(UPLOADS_DIR, CLEANUP_DELAY_MINUTES, SESSION_IDLE_MINUTES, BUSY_TIMEOUT_MINUTES)
    logger.info("Startup cleanup removed %d expired session dir(s)", removed)
    task = asyncio.create_task(
        cleanup_loop(UPLOADS_DIR, CLEANUP_DELAY_MINUTES, CLEANUP_INTERVAL_SECONDS,
                     SESSION_IDLE_MINUTES, BUSY_TIMEOUT_MINUTES)
    )
    logger.info(
        "Cleanup loop started (delay=%dmin, idle=%dmin, interval=%ds)",
        CLEANUP_DELAY_MINUTES,
        SESSION_IDLE_MINUTES,
        CLEANUP_INTERVAL_SECONDS,
    )
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Cleanup loop stopped")


app = FastAPI(title="PDF Toolbox", version=VERSION, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_cors_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]

# A ordem importa: o ultimo adicionado roda primeiro.
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
app.add_middleware(CSRFMiddleware, trusted_origins=_cors_origins)
app.add_middleware(
    BodySizeLimitMiddleware,
    max_bytes=MAX_UPLOAD_SIZE_MB * 1024 * 1024,
    max_mb=MAX_UPLOAD_SIZE_MB,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"error": "Erro interno do servidor"}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


app.include_router(pages.router)
app.include_router(merge.router, prefix="/api")
app.include_router(split.router, prefix="/api")
app.include_router(compress.router, prefix="/api")
app.include_router(extract.router, prefix="/api")
app.include_router(convert.router, prefix="/api")
app.include_router(detailed_merge.router, prefix="/api")
app.include_router(blank_remover.router, prefix="/api")
