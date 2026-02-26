# CLAUDE.md — Trans-Script Web

## Project Overview

Trans-Script Web is a full-stack application for automating PHP localization file translation from English (EN) to Brazilian Portuguese (PT-BR). It accepts ZIP/RAR/TAR archives containing PHP files with `$msg_arr` arrays, translates them via `translate-shell` (Google Translate), and returns downloadable ZIP archives.

**Stack**: Flask backend + React frontend + Nginx reverse proxy

## Repository Structure

```
translate-php-tool/
├── backend/                  # Flask API + WebSocket server (Python)
│   ├── app.py               # Main Flask app: REST routes, WebSocket handlers, security headers
│   ├── translator.py         # Job manager: archive extraction, file translation, progress
│   ├── translate.py          # Core translation engine (CLI + library), regex-based $msg_arr parsing
│   ├── auth.py               # OTP authentication, SQLite user DB, email sending
│   ├── config.py             # Centralized settings, logging setup
│   ├── wsgi.py               # Gunicorn entry point
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React SPA (Vite + Tailwind CSS)
│   ├── src/
│   │   ├── App.jsx           # Main component, router, job state
│   │   ├── main.jsx          # React DOM entry
│   │   ├── components/       # Header, FileUpload, TranslationProgress
│   │   ├── pages/            # LoginPage (OTP flow)
│   │   ├── hooks/            # useAuth (session), useSocket (WebSocket)
│   │   └── services/         # api.js (HTTP client), cache.js (localStorage TTL)
│   ├── vite.config.js        # Build → ../backend/static/, dev proxy to Flask
│   ├── tailwind.config.js
│   └── package.json
├── config/
│   ├── nginx.conf            # Reverse proxy template (port 80 → Flask 5000)
│   └── trans-script-web.service  # Systemd unit file
└── deploy.sh                 # Automated deployment script (Debian/Ubuntu)
```

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- `translate-shell` (`sudo apt install translate-shell`)
- `unrar` (for .rar archive support)

### Backend

```bash
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt
venv/bin/python -m flask --app backend.app run
# Runs on http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000, proxies /api and /socket.io to localhost:5000
```

### Production Build

```bash
cd frontend && npm run build   # Outputs to backend/static/
```

### Production Server

```bash
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -b 127.0.0.1:5000 backend.wsgi:app
```

### Automated Deployment

```bash
sudo ./deploy.sh   # Interactive, installs everything, sets up Nginx + systemd
```

## Environment Variables

Set in `/etc/trans-script-web/env` for production, or export directly for development:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | Random on startup | Flask session signing |
| `SMTP_HOST` | `smtp.gmail.com` | Email server for OTP |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASS` | *(empty)* | SMTP password |
| `SMTP_FROM` | `Trans-Script <noreply@example.com>` | Sender address |

If SMTP is not configured, OTP codes are logged to the console instead of being emailed.

## Key Technical Details

### Backend Architecture

- **Threading model**: Gevent-based async; translation jobs run in `threading.Thread`
- **Job registry**: In-memory dict protected by `threading.Lock()` — lost on restart
- **Database**: SQLite for user accounts and translation cache (`backend/users.db`)
- **Translation engine**: Regex-based `$msg_arr` line parser with placeholder protection (`{var}` → `__PH0__`)
- **WebSocket**: Flask-SocketIO for real-time progress; polling fallback built into frontend
- **File processing**: Archives extracted to `backend/uploads/`, results in `backend/jobs/`

### Frontend Architecture

- **Framework**: React 19 with functional components and hooks only (no class components)
- **Styling**: Tailwind CSS utility classes exclusively
- **Build**: Vite 6 with React plugin; output goes to `backend/static/`
- **State**: Local state via `useState`/`useCallback`/`useRef`; no external state library
- **Real-time**: Socket.IO client with automatic reconnection and polling fallback

### API Endpoints

- `GET /api/health` — Health check
- `POST /api/auth/request-otp` — Request OTP code
- `POST /api/auth/verify-otp` — Verify OTP code
- `GET /api/auth/me` — Check session
- `POST /api/auth/logout` — End session
- `POST /api/upload` — Upload archive for translation
- `GET /api/status/<job_id>` — Poll job status
- `GET /api/download/<job_id>` — Download translated archive

## Testing

There is no automated test suite. Current validation methods:

```bash
# Validate translation quality (CLI mode)
python3 backend/translate.py --validate --dir-in EN --dir-out BR

# Health check
curl http://localhost:5000/api/health
```

## Coding Conventions

### Python

- PEP 8 style: `snake_case` for functions/variables, `ALL_CAPS` for module constants
- 4-space indentation
- One responsibility per module (config, auth, translation, app)
- Context managers for SQLite connections (`_db_conn()`)
- Specific exception handling with logging via `logging.getLogger('trans-script')`
- Thread safety via `threading.Lock()` for shared state

### JavaScript/React

- Functional components only — no class components
- `camelCase` for functions/variables, `PascalCase` for components, `UPPER_CASE` for constants
- Custom hooks for shared logic (`useAuth`, `useSocket`)
- `async/await` with `try-catch` for API calls
- Tailwind utility classes for all styling (no custom CSS beyond `index.css` Tailwind imports)

### General

- Comments and commit messages are in Portuguese (Brazilian)
- No linter or formatter is configured — maintain existing style consistency
- No TypeScript — plain JavaScript with JSDoc where present
- Security: path traversal protection, rate limiting, session-based auth, security headers on all responses

## Important Constraints

- `backend/static/` is gitignored — it's generated by `npm run build`
- `backend/uploads/` and `backend/jobs/` are gitignored runtime directories
- Max upload size: 100 MB (enforced in `config.py` and `nginx.conf`)
- Max concurrent translation jobs: 3
- Rate limit: 5 seconds between uploads per IP
- Job IDs are 8-character hex strings validated by regex `^[a-f0-9]{8}$`
