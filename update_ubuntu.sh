#!/bin/bash
# =============================================================================
# FLBR Corp - Script de Atualizacao (rodar apos mudar o codigo no GitHub)
# Execute como root: sudo bash update_ubuntu.sh
# =============================================================================

set -e

APP_DIR="/opt/cobrança"
SERVICE_NAME="flbrcobranca"

echo "Atualizando FLBR Corp em $APP_DIR..."

cd "$APP_DIR"

# Puxar o codigo mais recente
git pull

# Atualizar dependencias se requirements.txt mudou
"$APP_DIR/venv/bin/pip" install -r requirements.txt -q

# Corrigir permissoes
chown -R flbr:flbr "$APP_DIR"

# Reiniciar o servico
systemctl restart "$SERVICE_NAME"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "OK - Servico reiniciado com sucesso."
    echo "Versao atual: $(cd $APP_DIR && git log -1 --format='%h %s')"
else
    echo "ERRO - Falha ao reiniciar. Verifique: journalctl -u $SERVICE_NAME -n 30"
    exit 1
fi
