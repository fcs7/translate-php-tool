#!/bin/bash
# =============================================================================
#  Deploy automatico — Trans-Script Web
#  Compativel: Debian 12 / Ubuntu 22+ e derivados
#
#  O que faz:
#    1. Instala dependencias do sistema (apt)
#    2. Cria virtualenv Python e instala libs
#    3. Compila frontend React (npm)
#    4. Configura Nginx (reverse proxy + WebSocket)
#    5. Cria e ativa servico systemd
#
#  Uso:
#    chmod +x deploy.sh && sudo ./deploy.sh
# =============================================================================

set -euo pipefail

# --- Variaveis ---
APP_NAME="trans-script-web"
INSTALL_DIR="/opt/$APP_NAME"
VENV_DIR="$INSTALL_DIR/venv"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_USER="${SUDO_USER:-$USER}"

# --- Cores ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
fail() { echo -e "${RED}  ✗${NC} $1"; exit 1; }

echo ""
echo "=================================================="
echo "  Trans-Script Web — Deploy Automatico"
echo "  Origem:  $SCRIPT_DIR"
echo "  Destino: $INSTALL_DIR"
echo "=================================================="
echo ""

# --- Verificar root ---
if [ "$EUID" -ne 0 ]; then
    fail "Execute com sudo: sudo ./deploy.sh"
fi

# =============================================================================
# 1. Dependencias do sistema
# =============================================================================
log "[1/6] Instalando dependencias do sistema..."

apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    nginx \
    nodejs npm \
    || fail "Falha ao instalar pacotes base"

# translate-shell: tenta via apt, senao instala manualmente
apt-get install -y -qq translate-shell 2>/dev/null \
    || (wget -q -O /usr/local/bin/trans \
            "https://raw.githubusercontent.com/soimort/translate-shell/gh-pages/trans" \
        && chmod +x /usr/local/bin/trans \
        && ok "translate-shell instalado via wget")

# unrar: pacote non-free, opcional (suporte a .rar)
apt-get install -y -qq unrar 2>/dev/null \
    || apt-get install -y -qq unrar-free 2>/dev/null \
    || echo "  ! unrar nao disponivel — arquivos .rar nao serao suportados"

ok "Pacotes instalados"

# =============================================================================
# 2. Copiar projeto para /opt
# =============================================================================
log "[2/6] Copiando projeto para $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"
rsync -a --exclude='venv' --exclude='node_modules' --exclude='.git' \
    --exclude='backend/uploads' --exclude='backend/jobs' --exclude='backend/static' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/"

# Criar diretorios de runtime
mkdir -p "$INSTALL_DIR/backend/uploads"
mkdir -p "$INSTALL_DIR/backend/jobs"
mkdir -p "$INSTALL_DIR/backend/static"
chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$INSTALL_DIR"

ok "Projeto copiado"

# =============================================================================
# 3. Python virtualenv + dependencias
# =============================================================================
log "[3/6] Configurando ambiente Python..."

sudo -u "$DEPLOY_USER" python3 -m venv "$VENV_DIR"
sudo -u "$DEPLOY_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$DEPLOY_USER" "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/backend/requirements.txt"

ok "Virtualenv pronto ($VENV_DIR)"

# =============================================================================
# 4. Frontend build
# =============================================================================
log "[4/6] Compilando frontend React..."

cd "$INSTALL_DIR/frontend"
sudo -u "$DEPLOY_USER" npm install --silent 2>/dev/null
sudo -u "$DEPLOY_USER" npm run build 2>/dev/null
cd "$INSTALL_DIR"

ok "Frontend compilado → backend/static/"

# =============================================================================
# 5. Nginx
# =============================================================================
log "[5/6] Configurando Nginx..."

cp "$INSTALL_DIR/config/nginx.conf" "/etc/nginx/sites-available/$APP_NAME"
ln -sf "/etc/nginx/sites-available/$APP_NAME" "/etc/nginx/sites-enabled/$APP_NAME"

# Remover default apenas se existir
[ -f /etc/nginx/sites-enabled/default ] && rm -f /etc/nginx/sites-enabled/default

nginx -t > /dev/null 2>&1 || fail "Configuracao Nginx invalida"
systemctl reload nginx

ok "Nginx configurado (porta 80)"

# =============================================================================
# 6. Systemd service
# =============================================================================
log "[6/6] Criando servico systemd..."

# Criar arquivo de env se ainda nao existir
ENV_FILE="/etc/trans-script-web/env"
mkdir -p "/etc/trans-script-web"
if [ ! -f "$ENV_FILE" ]; then
    GENERATED_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$ENV_FILE" << ENV
# Variaveis de ambiente — Trans-Script Web
# Edite com: nano $ENV_FILE
# Depois reinicie: systemctl restart $APP_NAME

SECRET_KEY=$GENERATED_KEY

# SMTP para envio de OTP (obrigatorio para producao)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=Trans-Script <noreply@example.com>
ENV
    chmod 600 "$ENV_FILE"
    ok "Arquivo de env criado: $ENV_FILE  (configure SMTP_USER e SMTP_PASS)"
else
    ok "Arquivo de env ja existe: $ENV_FILE"
fi

cat > "/etc/systemd/system/$APP_NAME.service" << UNIT
[Unit]
Description=Trans-Script Web — Tradutor PHP EN→PT-BR
After=network.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/gunicorn \\
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \\
    --workers 1 \\
    --bind 127.0.0.1:5000 \\
    --timeout 300 \\
    backend.wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$APP_NAME" > /dev/null 2>&1
systemctl restart "$APP_NAME"

sleep 2

if systemctl is-active --quiet "$APP_NAME"; then
    ok "Servico ativo"
else
    fail "Servico nao iniciou — veja: journalctl -u $APP_NAME -n 50"
fi

# =============================================================================
# Resultado
# =============================================================================
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=================================================="
echo -e "  ${GREEN}Deploy concluido com sucesso!${NC}"
echo ""
echo "  URL:      http://$IP"
echo "  Status:   systemctl status $APP_NAME"
echo "  Logs:     journalctl -u $APP_NAME -f"
echo "  Reiniciar: systemctl restart $APP_NAME"
echo "=================================================="
echo ""
