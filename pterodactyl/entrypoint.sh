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

echo "Python: $(python --version 2>&1)"
echo "LibreOffice: $(soffice --version 2>/dev/null | head -n 1)"

MODIFIED_STARTUP=$(echo -e "${STARTUP}" | sed -e 's/{{/${/g' -e 's/}}/}/g')
echo ":/home/container$ ${MODIFIED_STARTUP}"

# shellcheck disable=SC2086
eval ${MODIFIED_STARTUP}
