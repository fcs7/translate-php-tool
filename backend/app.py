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
    start_translation, get_job, delete_job, list_jobs,
    cleanup_old_jobs, count_running_jobs,
)
from backend.auth import (
    init_db, get_or_create_user,
    generate_otp, verify_otp, send_otp_email,
    clear_untranslated_cache,
)

# ============================================================================
# App
# ============================================================================

app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=30)
CORS(app, supports_credentials=True)

# Inicializar banco de dados
init_db()

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


# Rate limit simples: {ip: timestamp_ultimo_upload}
_upload_timestamps = {}

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
    session['user_email'] = email
    session.permanent = True
    log.info(f'[AUTH] Login: {email}')
    return jsonify({'user': user}), 200


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    email = session.pop('user_email', None)
    if email:
        log.info(f'[AUTH] Logout: {email}')
    return jsonify({'message': 'Logout realizado'}), 200


@app.route('/api/auth/me')
def auth_me():
    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Nao autenticado'}), 401
    user = get_or_create_user(email)
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
    """Recebe arquivo compactado com PHPs e inicia traducao."""
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

    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    f = request.files['file']
    allowed = ('.zip', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2')
    if not f.filename or not f.filename.lower().endswith(allowed):
        log.warning(f'{ip} arquivo rejeitado: {f.filename}')
        return jsonify({'error': 'Formatos aceitos: ZIP, RAR, TAR, TAR.GZ'}), 400

    ext = '.' + f.filename.rsplit('.', 1)[-1]
    filename = f"upload_{os.urandom(8).hex()}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)

    file_size = os.path.getsize(filepath)
    log.info(f'{ip} upload: {f.filename} ({file_size / 1024:.1f} KB)')

    delay = max(0.05, min(float(request.form.get('delay', 0.2)), 5.0))

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
        '<h1>Trans-Script Web</h1>'
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
    log.info('Servidor iniciando em http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
