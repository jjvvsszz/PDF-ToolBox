# syntax=docker/dockerfile:1
#
# Imagem para Pterodactyl (Wings): runtime + aplicacao embutida.
# Multi-arch (linux/arm64 para OCI Ampere, linux/amd64), publicada pelo
# workflow .github/workflows/painel-image.yml em ghcr.io/jjvvsszz/pdf-toolbox.
#
# O codigo fica em /app (somente leitura para o usuario do container);
# os dados (uploads, temporarios) ficam em /home/container, o volume do servidor.

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# LibreOffice sem interface grafica (Office -> PDF) e fontes metricamente
# compativeis com Calibri/Cambria/Arial/Times para manter o layout dos documentos.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libreoffice-writer-nogui \
        libreoffice-calc-nogui \
        libreoffice-impress-nogui \
        fonts-liberation2 \
        fonts-dejavu-core \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        tini \
        openssl \
        iproute2 \
        ca-certificates \
        tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && soffice --version

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt \
 && python -c "import fastapi, uvicorn, fitz, pikepdf, img2pdf, pdf2docx, cv2, numpy, PIL"

COPY app /app/app
COPY templates /app/templates
RUN python -m compileall -q /app/app

# Padrao dos yolks do Pterodactyl: usuario "container" com home no volume do servidor
RUN useradd --create-home --home-dir /home/container --shell /bin/bash container
COPY --chmod=755 pterodactyl/entrypoint.sh /entrypoint.sh

USER container
ENV USER=container \
    HOME=/home/container \
    UPLOADS_DIR=/home/container/uploads \
    TMPDIR=/home/container/tmp \
    LOG_FILE=/home/container/logs/app.log
WORKDIR /home/container

STOPSIGNAL SIGINT
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/entrypoint.sh"]

LABEL org.opencontainers.image.source="https://github.com/jjvvsszz/PDF-ToolBox" \
      org.opencontainers.image.description="PDF Toolbox para Pterodactyl (Python 3.11 + LibreOffice)" \
      org.opencontainers.image.licenses="NOASSERTION"
