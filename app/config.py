import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WORKERS = int(os.getenv("WORKERS", "4"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
# Opcional: tambem grava os logs (app + acessos) neste arquivo, para monitoramento
LOG_FILE = os.getenv("LOG_FILE", "")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_FILES = int(os.getenv("MAX_FILES", "50"))
CLEANUP_DELAY_MINUTES = int(os.getenv("CLEANUP_DELAY_MINUTES", "3"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))
# Sessoes interativas (mesclagem detalhada) ficam vivas por mais tempo sem atividade
SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "30"))
# Tempo maximo que um processamento pode manter a pasta protegida da limpeza
BUSY_TIMEOUT_MINUTES = int(os.getenv("BUSY_TIMEOUT_MINUTES", "60"))
OFFICE_TIMEOUT_SECONDS = int(os.getenv("OFFICE_TIMEOUT_SECONDS", "180"))
# Processos usados pela compressao extrema. Em containers o cpu_count() enxerga todos os
# nucleos do host, nao o limite de CPU do servidor, por isso o valor e configuravel.
COMPRESS_MAX_WORKERS = max(1, int(os.getenv("COMPRESS_MAX_WORKERS", "4")))

# Origens extras (separadas por virgula) autorizadas a chamar a API de outro dominio.
# Vazio = somente a mesma origem.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")

# No container o codigo fica em /app (somente leitura) e os dados no volume do servidor
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR") or BASE_DIR / "uploads")
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
