#!/bin/bash
# =============================================================================
#  Deploy automatico — Trans-Script Web
#  Compativel: Debian 12 / Ubuntu 22+ e derivados
#
#  O que faz:
#    0. Coleta configuracao SMTP interativamente (senha oculta)
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
ENV_FILE="/etc/trans-script-web/env"

# --- Cores ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1"; }
ok()   { echo -e "${GREEN}  ✓${NC} $1"; }
warn() { echo -e "${YELLOW}  !${NC} $1"; }
fail() { echo -e "${RED}  ✗${NC} $1"; exit 1; }

# --- Verificar root ---
if [ "$EUID" -ne 0 ]; then
    fail "Execute com sudo: sudo ./deploy.sh"
fi

echo ""
echo "=================================================="
echo "  Trans-Script Web — Deploy Automatico"
echo "  Origem:  $SCRIPT_DIR"
echo "  Destino: $INSTALL_DIR"
echo "=================================================="
echo ""

# =============================================================================
# 0. Configuracao SMTP (interativo — senha oculta)
# =============================================================================

SMTP_HOST_VAL="smtp.gmail.com"
SMTP_PORT_VAL="587"
SMTP_USER_VAL=""
SMTP_PASS_VAL=""
SMTP_FROM_VAL=""
SKIP_SMTP=0

if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Arquivo de configuracao ja existe:${NC} $ENV_FILE"
    echo ""
    read -r -p "  Reconfigurar SMTP? [s/N] " _resp
    echo ""
    if [[ ! "$_resp" =~ ^[Ss]$ ]]; then
        SKIP_SMTP=1
        ok "Configuracao SMTP mantida"
        echo ""
    fi
fi

if [ "$SKIP_SMTP" -eq 0 ]; then
    echo -e "${BLUE}Configuracao de e-mail (OTP)${NC}"
    echo "  O sistema envia codigos de acesso por e-mail."
    echo "  Para Gmail: use uma App Password (nao a senha da conta)."
    echo "  Saiba mais: https://myaccount.google.com/apppasswords"
    echo ""

    # SMTP_USER
    while true; do
        read -r -p "  E-mail remetente (ex: seu@gmail.com): " SMTP_USER_VAL
        SMTP_USER_VAL="${SMTP_USER_VAL// /}"
        if [[ "$SMTP_USER_VAL" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; then
            break
        fi
        warn "E-mail invalido. Tente novamente."
    done

    # SMTP_PASS (oculta)
    while true; do
        read -r -s -p "  Senha / App Password (nao aparece): " SMTP_PASS_VAL
        echo ""
        if [ -n "$SMTP_PASS_VAL" ]; then
            break
        fi
        warn "Senha nao pode ser vazia."
    done

    # SMTP_FROM (opcional)
    read -r -p "  Nome do remetente [Trans-Script]: " _from_name
    _from_name="${_from_name:-Trans-Script}"
    SMTP_FROM_VAL="$_from_name <$SMTP_USER_VAL>"

    # SMTP personalizado (opcional)
    read -r -p "  Servidor SMTP [$SMTP_HOST_VAL]: " _host
    SMTP_HOST_VAL="${_host:-$SMTP_HOST_VAL}"

    read -r -p "  Porta SMTP [$SMTP_PORT_VAL]: " _port
    SMTP_PORT_VAL="${_port:-$SMTP_PORT_VAL}"

    echo ""
    echo "  Resumo:"
    echo "    Servidor : $SMTP_HOST_VAL:$SMTP_PORT_VAL"
    echo "    Conta    : $SMTP_USER_VAL"
    echo "    Remetente: $SMTP_FROM_VAL"
    echo ""
    read -r -p "  Confirmar? [S/n] " _conf
    [[ "$_conf" =~ ^[Nn]$ ]] && fail "Cancelado pelo usuario."
    echo ""
fi

# =============================================================================
# 1. Dependencias do sistema
# =============================================================================
log "[1/6] Instalando dependencias do sistema..."

apt-get update -qq

# Corrigir pacotes quebrados antes de instalar qualquer coisa
apt-get install -f -y -qq 2>/dev/null || true
dpkg --configure -a 2>/dev/null || true

apt-get install -y \
    python3 python3-venv python3-pip \
    nginx \
    || fail "Falha ao instalar pacotes base (python3/nginx)"

# Node.js: tenta versao do sistema; se muito antiga (<18) instala via NodeSource
NODE_OK=0
if command -v node &>/dev/null && [ "$(node -e 'process.exit(parseInt(process.versions.node)<18?1:0)' 2>/dev/null; echo $?)" = "0" ]; then
    NODE_OK=1
fi
if [ "$NODE_OK" -eq 0 ]; then
    apt-get install -y nodejs npm 2>/dev/null && NODE_OK=1 || true
fi
if [ "$NODE_OK" -eq 0 ]; then
    warn "Instalando Node.js 20 via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y nodejs || fail "Falha ao instalar Node.js"
fi
ok "Node.js $(node -v) / npm $(npm -v)"

# translate-shell: tenta via apt, senao instala manualmente
apt-get install -y -qq translate-shell 2>/dev/null \
    || (wget -q -O /usr/local/bin/trans \
            "https://raw.githubusercontent.com/soimort/translate-shell/gh-pages/trans" \
        && chmod +x /usr/local/bin/trans \
        && ok "translate-shell instalado via wget")

# unrar: pacote non-free, opcional (suporte a .rar)
apt-get install -y -qq unrar 2>/dev/null \
    || apt-get install -y -qq unrar-free 2>/dev/null \
    || warn "unrar nao disponivel — arquivos .rar nao serao suportados"

ok "Pacotes instalados"

# =============================================================================
# 2. Copiar projeto para /opt
# =============================================================================
log "[2/6] Copiando projeto para $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"
rsync -a --exclude='venv' --exclude='node_modules' --exclude='.git' \
    --exclude='backend/uploads' --exclude='backend/jobs' --exclude='backend/static' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/"

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
sudo -u "$DEPLOY_USER" "$VENV_DIR/bin/pip" install --quiet \
    -r "$INSTALL_DIR/backend/requirements.txt"

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
[ -f /etc/nginx/sites-enabled/default ] && rm -f /etc/nginx/sites-enabled/default

nginx -t > /dev/null 2>&1 || fail "Configuracao Nginx invalida"
systemctl reload nginx

ok "Nginx configurado (porta 80)"

# =============================================================================
# 6. Arquivo de env + systemd
# =============================================================================
log "[6/6] Configurando servico systemd..."

mkdir -p "/etc/trans-script-web"
chmod 700 "/etc/trans-script-web"

# Gerar SECRET_KEY (sempre nova se o arquivo nao existia; manter se existia)
if [ "$SKIP_SMTP" -eq 0 ]; then
    SECRET_KEY_VAL=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Escrever env com permissao restrita (somente root le)
    install -m 600 /dev/null "$ENV_FILE"
    cat > "$ENV_FILE" << EOF
# Trans-Script Web — variaveis de ambiente
# Gerado em: $(date)
# Para alterar: nano $ENV_FILE && systemctl restart $APP_NAME

SECRET_KEY=$SECRET_KEY_VAL

SMTP_HOST=$SMTP_HOST_VAL
SMTP_PORT=$SMTP_PORT_VAL
SMTP_USER=$SMTP_USER_VAL
SMTP_PASS=$SMTP_PASS_VAL
SMTP_FROM=$SMTP_FROM_VAL
EOF
    chmod 600 "$ENV_FILE"
    chown root:root "$ENV_FILE"
    ok "Configuracao salva em $ENV_FILE (chmod 600)"
fi

# Escrever unit do systemd
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
    ok "Servico iniciado e habilitado no boot"
else
    echo ""
    echo "  Ultimas linhas do log:"
    journalctl -u "$APP_NAME" -n 20 --no-pager | sed 's/^/    /'
    fail "Servico nao iniciou — veja: journalctl -u $APP_NAME -f"
fi

# =============================================================================
# Resultado
# =============================================================================
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=================================================="
echo -e "  ${GREEN}Deploy concluido com sucesso!${NC}"
echo ""
echo "  URL:       http://$IP"
echo "  Env:       $ENV_FILE"
echo "  Status:    systemctl status $APP_NAME"
echo "  Logs:      journalctl -u $APP_NAME -f"
echo "  Reiniciar: systemctl restart $APP_NAME"
echo "=================================================="
echo ""
