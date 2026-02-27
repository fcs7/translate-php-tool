#!/usr/bin/env python3
"""
Trans-Script Web — Aplicacao Flask principal.
Monolito: serve API REST + WebSocket + frontend React (static).
"""

import os
import re
import time
from datetime import timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, send_file, session
from flask_cors import CORS
from flask_socketio import SocketIO, join_room

from backend.config import (
    UPLOAD_FOLDER, STATIC_FOLDER, MAX_CONTENT_LENGTH,
    MAX_CONCURRENT_JOBS, RATE_LIMIT_SECONDS, SECRET_KEY, log,
)
from backend.translator import (
    start_translation, start_translation_raw, get_job, delete_job, list_jobs,
    cleanup_old_jobs, count_running_jobs,
)
from backend.auth import (
    init_db, get_or_create_user, list_all_users, get_system_stats, get_user_by_id,
    generate_otp, verify_otp, send_otp_email,
    clear_untranslated_cache,
)
from backend.admin_auth import (
    init_admin_db, create_admin_session, validate_admin_session,
    revoke_admin_session, revoke_all_admin_sessions,
    is_admin, set_admin, list_admins, list_active_sessions,
    cleanup_expired_sessions,
)
from backend.config import ADMIN_EMAILS

# ============================================================================
# App
# ============================================================================

from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')

# Confiar em 1 proxy (Nginx) para X-Forwarded-For e X-Forwarded-Proto
# Garante que request.remote_addr reflita o IP real do cliente
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)

# Session cookie security
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Em producao (HTTPS): descomentar ou definir via env
# app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')

CORS(app, supports_credentials=True)

# Inicializar banco de dados
init_db()
init_admin_db()

# Auto-promover admins listados em ADMIN_EMAILS
for _admin_email in ADMIN_EMAILS:
    get_or_create_user(_admin_email)
    set_admin(_admin_email, True)

try:
    import gevent  # noqa: F401
    _async_mode = 'gevent'
except ImportError:
    _async_mode = 'threading'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_mode)

# ============================================================================
# Autenticacao
# ============================================================================

def login_required(f):
    """Decorator: exige sessao ativa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Autenticacao necessaria'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    Decorator: exige sessao admin valida.
    Verifica token no header Authorization: Bearer <token>
    com validacao AES-256-GCM + HMAC-SHA256 + IP binding.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token admin ausente'}), 401

        token = auth_header[7:]
        admin_session = validate_admin_session(token, request.remote_addr)
        if not admin_session:
            return jsonify({'error': 'Sessao admin invalida ou expirada'}), 401

        # Injetar dados do admin no request context
        request.admin_email = admin_session['email']
        request.admin_session = admin_session
        return f(*args, **kwargs)
    return decorated


# Rate limit simples: {ip: timestamp_ultimo_upload}
_upload_timestamps = {}

# Rate limit para tentativas de admin login: {ip: [timestamp, ...]}
_admin_login_attempts = {}
_ADMIN_LOGIN_MAX_ATTEMPTS = 5
_ADMIN_LOGIN_WINDOW = 300  # 5 minutos

# Regex para validar job_id (apenas hex, 8 chars)
_JOB_ID_RE = re.compile(r'^[a-f0-9]{8}$')


# ============================================================================
# Seguranca — headers em todas as respostas
# ============================================================================

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# ============================================================================
# Logging — toda requisicao
# ============================================================================

@app.before_request
def log_request():
    if request.path.startswith('/api'):
        log.info(f'{request.remote_addr} {request.method} {request.path}')


# ============================================================================
# Helpers
# ============================================================================

def _validate_job_id(job_id):
    """Valida formato do job_id para evitar path traversal."""
    return bool(_JOB_ID_RE.match(job_id))


def _check_rate_limit(ip):
    """Retorna True se o IP esta dentro do rate limit."""
    now = time.time()
    last = _upload_timestamps.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _upload_timestamps[ip] = now
    return True


# ============================================================================
# Rotas de autenticacao
# ============================================================================

@app.route('/api/auth/request-otp', methods=['POST'])
def auth_request_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'E-mail invalido'}), 400

    code, remaining = generate_otp(email)
    if code is None:
        return jsonify({'error': f'Aguarde {remaining}s para solicitar um novo codigo'}), 429

    try:
        send_otp_email(email, code)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500

    log.info(f'[AUTH] OTP solicitado: {email}')
    return jsonify({'message': 'Codigo enviado'}), 200


@app.route('/api/auth/verify-otp', methods=['POST'])
def auth_verify_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()

    if not email or not code:
        return jsonify({'error': 'E-mail e codigo sao obrigatorios'}), 400

    ok, reason = verify_otp(email, code)
    if not ok:
        return jsonify({'error': reason}), 401

    user = get_or_create_user(email)
    user['is_admin'] = is_admin(email)
    session['user_email'] = email
    session.permanent = True
    log.info(f'[AUTH] Login: {email}')
    return jsonify({'user': user}), 200


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    email = session.pop('user_email', None)
    if email:
        # Revogar sessoes admin ao fazer logout geral
        if is_admin(email):
            revoke_all_admin_sessions(email)
        log.info(f'[AUTH] Logout: {email}')
    session.clear()
    return jsonify({'message': 'Logout realizado'}), 200


@app.route('/api/auth/me')
def auth_me():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Nao autenticado'}), 401
    user = get_or_create_user(email)
    user['is_admin'] = is_admin(email)
    return jsonify({'user': user}), 200


# ============================================================================
# API REST
# ============================================================================

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'trans-script-web'})


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Recebe arquivo compactado ou arquivos PHP avulsos e inicia traducao."""
    ip = request.remote_addr

    # Rate limit
    if not _check_rate_limit(ip):
        log.warning(f'{ip} rate limited (upload)')
        return jsonify({'error': f'Aguarde {RATE_LIMIT_SECONDS}s entre uploads'}), 429

    # Limite de jobs simultaneos
    running = count_running_jobs()
    if running >= MAX_CONCURRENT_JOBS:
        log.warning(f'{ip} bloqueado: {running} jobs rodando (max {MAX_CONCURRENT_JOBS})')
        return jsonify({'error': f'Limite de {MAX_CONCURRENT_JOBS} traducoes simultaneas'}), 429

    delay = max(0.05, min(float(request.form.get('delay', 0.2)), 5.0))

    # ── Modo 2: multiplos arquivos PHP avulsos ──────────────────────────────
    raw_files = request.files.getlist('files')
    if raw_files:
        paths = request.form.getlist('paths')

        # Validar: todos devem ser .php
        for i, f in enumerate(raw_files):
            if not f.filename or not f.filename.lower().endswith('.php'):
                log.warning(f'{ip} arquivo PHP rejeitado: {f.filename}')
                return jsonify({'error': f'Arquivo nao e .php: {f.filename}'}), 400

        # Salvar arquivos em diretorio temporario preservando caminhos relativos
        tmp_dir = os.path.join(UPLOAD_FOLDER, f"raw_{os.urandom(8).hex()}")
        total_size = 0

        try:
            for i, f in enumerate(raw_files):
                # Usar caminho relativo se fornecido, senao nome do arquivo
                rel_path = paths[i] if i < len(paths) else f.filename
                # Sanitizar: remover prefixo de pasta raiz do webkitdirectory
                # (ex: "minha_pasta/sub/file.php" -> "sub/file.php" ou "file.php")
                parts = rel_path.replace('\\', '/').split('/')
                if len(parts) > 1:
                    # Remover primeiro nivel (nome da pasta selecionada)
                    rel_path = '/'.join(parts[1:])
                else:
                    rel_path = parts[0]

                # Prevenir path traversal
                safe_path = os.path.normpath(rel_path)
                if safe_path.startswith('..') or os.path.isabs(safe_path):
                    return jsonify({'error': f'Caminho invalido: {rel_path}'}), 400

                dest = os.path.join(tmp_dir, safe_path)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                f.save(dest)
                total_size += os.path.getsize(dest)

            log.info(f'{ip} upload: {len(raw_files)} arquivos PHP ({total_size / 1024:.1f} KB)')

            job_id = start_translation_raw(tmp_dir, delay, socketio, user_email=session['user_email'])
            log.info(f'{ip} job criado: {job_id} (delay={delay}s, {len(raw_files)} arquivos PHP)')
            return jsonify({'job_id': job_id}), 201

        except Exception as e:
            log.error(f'{ip} erro ao criar job (PHP avulsos): {e}')
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({'error': str(e)}), 500

    # ── Modo 1: arquivo compactado (ZIP, RAR, TAR) ─────────────────────────
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    f = request.files['file']
    allowed = ('.zip', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2')
    if not f.filename or not f.filename.lower().endswith(allowed):
        log.warning(f'{ip} arquivo rejeitado: {f.filename}')
        return jsonify({'error': 'Formatos aceitos: ZIP, RAR, TAR, TAR.GZ ou arquivos .php'}), 400

    ext = '.' + f.filename.rsplit('.', 1)[-1]
    filename = f"upload_{os.urandom(8).hex()}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)

    file_size = os.path.getsize(filepath)
    log.info(f'{ip} upload: {f.filename} ({file_size / 1024:.1f} KB)')

    try:
        job_id = start_translation(filepath, delay, socketio, user_email=session['user_email'])
        os.remove(filepath)
        log.info(f'{ip} job criado: {job_id} (delay={delay}s)')
        return jsonify({'job_id': job_id}), 201
    except Exception as e:
        log.error(f'{ip} erro ao criar job: {e}')
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs')
@login_required
def get_jobs():
    return jsonify(list_jobs(session['user_email']))


@app.route('/api/jobs/<job_id>')
@login_required
def get_job_status(job_id):
    if not _validate_job_id(job_id):
        return jsonify({'error': 'ID invalido'}), 400
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job nao encontrado'}), 404
    if job.user_email != session['user_email']:
        return jsonify({'error': 'Acesso negado'}), 403
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>/download')
@login_required
def download_job(job_id):
    if not _validate_job_id(job_id):
        return jsonify({'error': 'ID invalido'}), 400
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job nao encontrado'}), 404
    if job.user_email != session['user_email']:
        return jsonify({'error': 'Acesso negado'}), 403
    if job.status != 'completed' or not job.output_zip:
        return jsonify({'error': 'Traducao ainda nao concluida'}), 400
    log.info(f'{request.remote_addr} download: {job_id}')
    return send_file(
        job.output_zip,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'traducao_{job_id}.zip',
    )


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
@login_required
def remove_job(job_id):
    if not _validate_job_id(job_id):
        return jsonify({'error': 'ID invalido'}), 400
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job nao encontrado'}), 404
    if job.user_email != session['user_email']:
        return jsonify({'error': 'Acesso negado'}), 403
    delete_job(job_id)
    log.info(f'{request.remote_addr} deletou job: {job_id}')
    return jsonify({'message': 'Job removido'})


@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    if not _validate_job_id(job_id):
        return jsonify({'error': 'ID invalido'}), 400
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job nao encontrado'}), 404
    if job.user_email != session['user_email']:
        return jsonify({'error': 'Acesso negado'}), 403
    if job.status != 'running':
        return jsonify({'error': 'Job nao esta em execucao'}), 400
    job.cancel()
    log.info(f'{request.remote_addr} cancelou job: {job_id}')
    return jsonify({'message': 'Cancelamento solicitado'})


# ============================================================================
# Manutencao de cache
# ============================================================================

@app.route('/api/cache/clear-untranslated', methods=['POST'])
@login_required
def clear_cache():
    """Remove traducoes falhadas do cache (source == translated)."""
    deleted = clear_untranslated_cache()
    log.info(f'{request.remote_addr} limpou cache: {deleted} entradas removidas')
    return jsonify({'deleted': deleted, 'message': f'{deleted} traducoes falhadas removidas do cache'})


@app.route('/api/engine/stats')
@login_required
def engine_stats():
    """Retorna metricas da engine de traducao (providers, cache, status)."""
    from backend.engine import get_engine
    return jsonify(get_engine().get_stats())


# ============================================================================
# Admin — Sessao
# ============================================================================

@app.route('/api/admin/login', methods=['POST'])
@login_required
def admin_login():
    """
    Gera token admin seguro para usuario que ja esta logado e e admin.
    Token: 384-bit entropy + HMAC-SHA256 + sessao server-side com AES-256-GCM.
    """
    ip = request.remote_addr

    # Rate limit de tentativas de admin login por IP
    now = time.time()
    attempts = _admin_login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < _ADMIN_LOGIN_WINDOW]
    if len(attempts) >= _ADMIN_LOGIN_MAX_ATTEMPTS:
        log.warning(f'[ADMIN] Rate limit atingido para IP {ip}')
        return jsonify({'error': 'Muitas tentativas. Aguarde 5 minutos.'}), 429

    email = session['user_email']

    if not is_admin(email):
        attempts.append(now)
        _admin_login_attempts[ip] = attempts
        log.warning(f'[ADMIN] Tentativa de login admin negada: {email} ({ip})')
        return jsonify({'error': 'Acesso negado'}), 403

    token = create_admin_session(email, ip)
    if not token:
        return jsonify({'error': 'Erro ao criar sessao admin'}), 500

    # Limpar tentativas em caso de sucesso
    _admin_login_attempts.pop(ip, None)

    return jsonify({
        'token': token,
        'message': 'Sessao admin criada',
    }), 200


@app.route('/api/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    """Revoga sessao admin atual."""
    auth_header = request.headers.get('Authorization', '')
    token = auth_header[7:]  # Remove 'Bearer '
    revoke_admin_session(token)
    return jsonify({'message': 'Sessao admin revogada'}), 200


@app.route('/api/admin/me')
@admin_required
def admin_me():
    """Retorna dados da sessao admin."""
    return jsonify({
        'email': request.admin_email,
        'is_admin': True,
        'session': {
            'created_at': request.admin_session['created_at'],
            'ip': request.admin_session['ip'],
        },
    })


# ============================================================================
# Admin — Gestao de usuarios
# ============================================================================

@app.route('/api/admin/users')
@admin_required
def admin_list_users():
    """Lista todos os usuarios com status admin."""
    return jsonify(list_all_users())


@app.route('/api/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_user(user_id):
    """Promove ou rebaixa usuario a admin."""
    row = get_user_by_id(user_id)
    if not row:
        return jsonify({'error': 'Usuario nao encontrado'}), 404

    new_status = not bool(row['is_admin'])

    # Impedir remocao do ultimo admin
    if not new_status:
        current_admins = list_admins()
        if len(current_admins) <= 1:
            return jsonify({'error': 'Impossivel remover o ultimo admin do sistema'}), 400

    set_admin(row['email'], new_status)
    action = 'promovido a admin' if new_status else 'removido de admin'
    return jsonify({'message': f'{row["email"]} {action}', 'is_admin': new_status})


@app.route('/api/admin/admins')
@admin_required
def admin_list_admins():
    """Lista todos os admins."""
    return jsonify(list_admins())


@app.route('/api/admin/sessions')
@admin_required
def admin_list_sessions():
    """Lista sessoes admin ativas."""
    return jsonify(list_active_sessions())


@app.route('/api/admin/sessions/revoke-all', methods=['POST'])
@admin_required
def admin_revoke_all():
    """Revoga todas as sessoes de um admin (exceto a propria)."""
    data = request.get_json(silent=True) or {}
    target_email = data.get('email', '').strip().lower()
    if not target_email:
        return jsonify({'error': 'E-mail obrigatorio'}), 400
    count = revoke_all_admin_sessions(target_email)
    return jsonify({'revoked': count, 'message': f'{count} sessoes revogadas'})


# ============================================================================
# Admin — Gestao de jobs (todos os usuarios)
# ============================================================================

@app.route('/api/admin/jobs')
@admin_required
def admin_list_all_jobs():
    """Lista todos os jobs de todos os usuarios (visao admin)."""
    all_jobs = list_jobs()  # Sem filtro de email
    return jsonify(all_jobs)


@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Estatisticas gerais do sistema."""
    stats = get_system_stats()
    active_sessions_list = list_active_sessions()

    stats.update({
        'running_jobs': count_running_jobs(),
        'max_concurrent_jobs': MAX_CONCURRENT_JOBS,
        'active_admin_sessions': len(active_sessions_list),
    })

    return jsonify(stats)


# ============================================================================
# WebSocket
# ============================================================================

@socketio.on('connect')
def ws_connect():
    log.debug(f'WS conectado: {request.remote_addr}')


@socketio.on('disconnect')
def ws_disconnect():
    log.debug(f'WS desconectado: {request.remote_addr}')


@socketio.on('join_job')
def ws_join_job(data):
    if 'user_email' not in session:
        return
    job_id = data.get('job_id', '')
    if not _validate_job_id(job_id):
        return
    job = get_job(job_id)
    if not job or job.user_email != session['user_email']:
        return
    join_room(job_id)
    log.debug(f'WS join_job: {job_id} ({request.remote_addr})')
    socketio.emit('translation_progress', job.to_dict(), room=job_id)


# ============================================================================
# Frontend SPA (React build)
# ============================================================================

@app.route('/')
def serve_index():
    index = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index):
        return send_from_directory(STATIC_FOLDER, 'index.html')
    return (
        '<html><body style="font-family:sans-serif;padding:40px;text-align:center">'
        '<h1>Traducao</h1>'
        '<p>Frontend nao compilado. Execute: <code>cd frontend &amp;&amp; npm run build</code></p>'
        '</body></html>'
    )


@app.route('/<path:path>')
def serve_static(path):
    full = os.path.join(STATIC_FOLDER, path)
    if os.path.exists(full):
        return send_from_directory(STATIC_FOLDER, path)
    index = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index):
        return send_from_directory(STATIC_FOLDER, 'index.html')
    return jsonify({'error': 'Not found'}), 404


# ============================================================================
# Entry-point de desenvolvimento
# ============================================================================

if __name__ == '__main__':
    cleanup_old_jobs()
    cleanup_expired_sessions()
    log.info('Servidor iniciando em http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
