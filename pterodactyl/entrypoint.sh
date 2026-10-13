#!/bin/bash
# Entrypoint no padrao dos yolks do Pterodactyl: o Wings passa o comando de
# inicializacao do egg em $STARTUP, com as variaveis no formato {{VAR}}.
cd /home/container || exit 1

INTERNAL_IP=$(ip route get 1 2>/dev/null | awk '{print $(NF-2); exit}')
export INTERNAL_IP

# O Wings monta /tmp como tmpfs pequeno (100 MB por padrao). Uploads grandes e o
# LibreOffice usam TMPDIR, que aponta para o volume do servidor.
mkdir -p "${UPLOADS_DIR}" "${TMPDIR}"
case "${TMPDIR}" in
    /home/container/*) find "${TMPDIR}" -mindepth 1 -delete 2>/dev/null ;;
esac

# Log em arquivo (lido pela rotina de monitoramento). Rotaciona na inicializacao
# para nao competir entre workers: mantem o arquivo atual e um anterior.
if [ -n "${LOG_FILE}" ]; then
    mkdir -p "$(dirname "${LOG_FILE}")"
    if [ -f "${LOG_FILE}" ] && [ "$(stat -c %s "${LOG_FILE}")" -gt 10485760 ]; then
        mv -f "${LOG_FILE}" "${LOG_FILE}.1"
    fi
fi

# HTTPS na origem (padrao do painel: Cloudflare com SSL Full). Usa ssl/cert.pem e
# ssl/key.pem do servidor; se nao existirem, gera um certificado autoassinado.
if [ "${HTTPS:-1}" = "1" ]; then
    SSL_DIR=/home/container/ssl
    if [ ! -s "${SSL_DIR}/cert.pem" ] || [ ! -s "${SSL_DIR}/key.pem" ]; then
        mkdir -p "${SSL_DIR}"
        echo "Gerando certificado autoassinado em ${SSL_DIR}"
        openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
            -subj "/CN=pdf-toolbox" \
            -keyout "${SSL_DIR}/key.pem" -out "${SSL_DIR}/cert.pem" 2>/dev/null \
            || { echo "ERRO: falha ao gerar o certificado"; exit 1; }
        chmod 600 "${SSL_DIR}/key.pem"
    fi
    # O uvicorn le estas variaveis como --ssl-keyfile/--ssl-certfile
    export UVICORN_SSL_KEYFILE="${SSL_DIR}/key.pem"
    export UVICORN_SSL_CERTFILE="${SSL_DIR}/cert.pem"
    echo "HTTPS: ativado"
else
    echo "HTTPS: desativado (HTTP puro)"
fi

echo "Python: $(python --version 2>&1)"
echo "LibreOffice: $(soffice --version 2>/dev/null | head -n 1)"

MODIFIED_STARTUP=$(echo -e "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g')
echo ":/home/container$ ${MODIFIED_STARTUP}"

# shellcheck disable=SC2086
eval ${MODIFIED_STARTUP}
