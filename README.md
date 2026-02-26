# Trans-Script Web

Aplicação web para tradução automática de arquivos de localização PHP (EN → PT-BR).

Faça upload de um `.zip` com seus arquivos PHP, acompanhe o progresso em tempo real e baixe o resultado traduzido.

---

## Como funciona

1. Upload de arquivo `.zip`, `.rar` ou `.tar.gz` contendo PHPs no formato `$msg_arr`
2. Backend Flask processa a tradução usando `translate-shell`
3. Progresso via WebSocket em tempo real no frontend React
4. Download do `.zip` com os arquivos traduzidos

---

## Requisitos

- Debian 12 / Ubuntu 22+ (ou derivados)
- Python 3.10+
- Node.js 18+
- Nginx
- `translate-shell`

---

## Instalação no Debian (Deploy automático)

```bash
# 1. Clonar o repositório
git clone https://github.com/fcs7/translate-php-tool.git
cd translate-php-tool

# 2. Executar o deploy (instala tudo automaticamente)
chmod +x deploy.sh
sudo ./deploy.sh
```

O script `deploy.sh` faz automaticamente:
- Instala dependências via `apt` (Python, Node.js, Nginx, translate-shell)
- Cria virtualenv Python e instala as libs
- Compila o frontend React (`npm run build`)
- Configura o Nginx como reverse proxy
- Cria e ativa o serviço systemd

Ao final, a aplicação estará disponível em `http://IP_DO_SERVIDOR`.

---

## Configuração manual (passo a passo)

### 1. Dependências do sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx nodejs npm translate-shell unrar
```

### 2. Copiar o projeto

```bash
sudo mkdir -p /opt/trans-script-web
sudo rsync -a --exclude='venv' --exclude='node_modules' --exclude='.git' \
    ./ /opt/trans-script-web/
sudo mkdir -p /opt/trans-script-web/backend/{uploads,jobs,static}
sudo chown -R $USER:$USER /opt/trans-script-web
```

### 3. Ambiente Python

```bash
cd /opt/trans-script-web
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r backend/requirements.txt
```

### 4. Compilar o frontend React

```bash
cd /opt/trans-script-web/frontend
npm install
npm run build
# O build vai para backend/static/ automaticamente
```

### 5. Configurar Nginx

```bash
sudo cp config/nginx.conf /etc/nginx/sites-available/trans-script-web
sudo ln -s /etc/nginx/sites-available/trans-script-web /etc/nginx/sites-enabled/trans-script-web
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

O arquivo `config/nginx.conf` configura:
- Reverse proxy da porta 80 → Flask na porta 5000
- Suporte a WebSocket (`/socket.io`)
- Timeout estendido para traduções longas (`/api` → 300s)
- Upload de até 100 MB

### 6. Serviço systemd

```bash
sudo cp config/trans-script-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trans-script-web
sudo systemctl start trans-script-web
```

Verificar se está rodando:
```bash
systemctl status trans-script-web
```

---

## SSL com Certbot (HTTPS)

O Nginx suporta SSL via terminação no proxy. Para habilitar HTTPS com certificado gratuito (Let's Encrypt):

### Pré-requisito

O servidor precisa ter um domínio apontado para ele (não funciona com IP diretamente).

### Instalar Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### Emitir e configurar o certificado

```bash
sudo certbot --nginx -d seu-dominio.com
```

O Certbot modifica automaticamente o Nginx para:
- Redirecionar HTTP → HTTPS
- Configurar o certificado SSL
- Renovar automaticamente (via cron/systemd)

### Verificar renovação automática

```bash
sudo certbot renew --dry-run
```

### Nginx com SSL (configuração manual)

Se preferir configurar manualmente em `config/nginx.conf`:

```nginx
server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name seu-dominio.com;

    ssl_certificate     /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        "upgrade";
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_read_timeout 86400;
    }

    location /api {
        proxy_pass http://127.0.0.1:5000/api;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
    }
}
```

---

## Gerenciamento do serviço

```bash
# Status
systemctl status trans-script-web

# Logs em tempo real
journalctl -u trans-script-web -f

# Reiniciar
systemctl restart trans-script-web

# Parar
systemctl stop trans-script-web
```

---

## API REST

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/health` | Status do servidor |
| `POST` | `/api/upload` | Upload de arquivo para tradução |
| `GET` | `/api/jobs` | Listar todos os jobs |
| `GET` | `/api/jobs/<id>` | Status de um job |
| `GET` | `/api/jobs/<id>/download` | Download do resultado |
| `POST` | `/api/jobs/<id>/cancel` | Cancelar job em execução |
| `DELETE` | `/api/jobs/<id>` | Remover job |

**Parâmetros do upload (`POST /api/upload`):**
- `file`: arquivo `.zip`, `.rar`, `.tar.gz` (máx. 100 MB)
- `delay`: intervalo entre traduções em segundos (padrão: `0.2`, mín: `0.05`, máx: `5.0`)

---

## Limites padrão

| Configuração | Valor |
|---|---|
| Tamanho máximo de upload | 100 MB |
| Jobs simultâneos | 3 |
| Rate limit por IP | 5s entre uploads |
| Timeout de tradução (Nginx) | 300s |

---

## Estrutura do projeto

```
.
├── backend/
│   ├── app.py          # Flask — API REST + WebSocket + serve SPA
│   ├── translator.py   # Engine de tradução (jobs, workers)
│   ├── config.py       # Configurações centralizadas
│   ├── wsgi.py         # Entry-point para Gunicorn
│   └── requirements.txt
├── frontend/
│   └── src/            # React + Tailwind CSS
├── config/
│   ├── nginx.conf               # Config Nginx pronta para uso
│   └── trans-script-web.service # Unit systemd
└── deploy.sh           # Script de deploy automático
```

---

## Problemas comuns

### Serviço não inicia

```bash
journalctl -u trans-script-web -n 50
```

### Nginx retorna 502 Bad Gateway

O Flask não está rodando. Verifique:
```bash
systemctl status trans-script-web
systemctl restart trans-script-web
```

### `translate-shell` não encontrado

```bash
sudo apt install translate-shell
# ou
sudo snap install translate-shell
```

### Upload rejeitado (413)

Verifique `client_max_body_size` no `nginx.conf` e `MAX_CONTENT_LENGTH` em `backend/config.py`.

---

Licença: MIT
