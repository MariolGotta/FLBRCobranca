#!/bin/bash
# =============================================================================
# FLBR Corp - Script de Deploy para Ubuntu Server 25
# Instala e configura o app em /opt/cobrança
#
# Como usar:
#   1. Copie este script para o servidor Ubuntu
#   2. Execute como root: sudo bash deploy_ubuntu.sh
# =============================================================================

set -e

APP_DIR="/opt/cobrança"
APP_USER="flbr"
REPO_URL="https://github.com/MariolGotta/FLBRCobranca.git"
PORT=30000
SERVICE_NAME="flbrcobranca"

echo "======================================================"
echo " FLBR Corp - Deploy Ubuntu Server"
echo " Destino: $APP_DIR | Porta: $PORT"
echo "======================================================"

# ---------------------------------------------------------------------------
# 1. Dependencias do sistema
# ---------------------------------------------------------------------------
echo ""
echo "[1/7] Instalando dependencias do sistema..."
apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    ufw

echo "OK - Python $(python3 --version)"

# ---------------------------------------------------------------------------
# 2. Criar usuario dedicado (sem shell, sem senha)
# ---------------------------------------------------------------------------
echo ""
echo "[2/7] Configurando usuario do servico..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
    echo "OK - Usuario '$APP_USER' criado."
else
    echo "OK - Usuario '$APP_USER' ja existe."
fi

# ---------------------------------------------------------------------------
# 3. Clonar ou atualizar o repositorio
# ---------------------------------------------------------------------------
echo ""
echo "[3/7] Clonando repositorio em $APP_DIR..."
if [ -d "$APP_DIR/.git" ]; then
    echo "Repositorio ja existe, atualizando..."
    cd "$APP_DIR"
    git pull
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi
echo "OK - Codigo atualizado."

# ---------------------------------------------------------------------------
# 4. Ambiente virtual Python e dependencias pip
# ---------------------------------------------------------------------------
echo ""
echo "[4/7] Configurando ambiente virtual Python..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
echo "OK - Dependencias pip instaladas."

# ---------------------------------------------------------------------------
# 5. Arquivo de configuracao de ambiente (.env)
# ---------------------------------------------------------------------------
echo ""
echo "[5/7] Configurando variaveis de ambiente..."
ENV_FILE="$APP_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    # Gerar SECRET_KEY aleatorio
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET
DATA_DIR=$APP_DIR/database
PORT=$PORT
EOF
    echo "OK - .env criado com SECRET_KEY gerado automaticamente."
else
    echo "OK - .env ja existe, mantendo configuracao atual."
fi

# Garantir que o diretorio de banco existe e tem permissao correta
mkdir -p "$APP_DIR/database"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
echo "OK - Permissoes configuradas para '$APP_USER'."

# ---------------------------------------------------------------------------
# 6. Servico systemd
# ---------------------------------------------------------------------------
echo ""
echo "[6/7] Configurando servico systemd..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=FLBR Corp - Sistema de Cobranca
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:$PORT --timeout 120 "app:create_app()"
Restart=on-failure
RestartSec=5

# Segurança
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR/database

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "OK - Servico '$SERVICE_NAME' rodando."
else
    echo "ERRO - Servico nao iniciou. Verifique: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# ---------------------------------------------------------------------------
# 7. Firewall UFW
# ---------------------------------------------------------------------------
echo ""
echo "[7/7] Configurando firewall..."
ufw allow "$PORT/tcp" comment "FLBR Corp webapp" > /dev/null
ufw --force enable > /dev/null
echo "OK - Porta $PORT liberada no UFW."

# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "======================================================"
echo " Deploy concluido com sucesso!"
echo ""
echo " URL de acesso: http://$SERVER_IP:$PORT"
echo ""
echo " Comandos uteis:"
echo "   Ver logs:     journalctl -u $SERVICE_NAME -f"
echo "   Reiniciar:    systemctl restart $SERVICE_NAME"
echo "   Parar:        systemctl stop $SERVICE_NAME"
echo "   Atualizar:    cd $APP_DIR && sudo bash update_ubuntu.sh"
echo "======================================================"
