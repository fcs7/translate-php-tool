"""
Servico de traducao — integra com translate.py do projeto.
Importa funcoes do script existente e adiciona progresso via WebSocket.
"""

import os
import shutil
import subprocess
import tarfile
import time
import zipfile
import uuid
import threading
from datetime import datetime

import backend.translate as trans_engine

from backend.config import JOBS_FOLDER, DEFAULT_DELAY, log
from backend.auth import get_cached_translation_db, save_cached_translation_db


# ============================================================================
# Model — Job de traducao
# ============================================================================

class TranslationJob:
    """Representa um job de traducao com estado e progresso."""

    def __init__(self, job_id, input_dir, output_dir, delay=DEFAULT_DELAY, user_email=''):
        self.job_id = job_id
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.delay = delay
        self.user_email = user_email

        # Estado
        self.status = 'pending'
        self.progress = 0
        self.current_file = ''
        self.total_files = 0
        self.files_done = 0
        self.total_strings = 0
        self.translated_strings = 0
        self.errors = []
        self.validation = None
        self.output_tar = None

        # Timestamps
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.finished_at = None

        # Controle interno
        self._cancel_flag = False

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'status': self.status,
            'progress': self.progress,
            'current_file': self.current_file,
            'total_files': self.total_files,
            'files_done': self.files_done,
            'total_strings': self.total_strings,
            'translated_strings': self.translated_strings,
            'errors': self.errors[-10:],
            'created_at': self.created_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'has_output': self.output_tar is not None,
            'validation': self.validation,
            'user_email': self.user_email,
        }

    def cancel(self):
        self._cancel_flag = True


# ============================================================================
# Registro global de jobs (em memoria)
# ============================================================================

_jobs = {}
_jobs_lock = threading.Lock()


def _get(job_id):
    with _jobs_lock:
        return _jobs.get(job_id)


def _put(job):
    with _jobs_lock:
        _jobs[job.job_id] = job


def _pop(job_id):
    with _jobs_lock:
        return _jobs.pop(job_id, None)


def count_running_jobs():
    """Conta quantos jobs estao em execucao."""
    with _jobs_lock:
        return sum(1 for j in _jobs.values() if j.status == 'running')


# ============================================================================
# Helpers de extracao (ZIP, RAR, TAR)
# ============================================================================

ALLOWED_EXTENSIONS = ('.zip', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2')


def _safe_zip_extract(zf, extract_to):
    """Extrai ZIP validando cada membro contra path traversal (ZIP Slip)."""
    target = os.path.realpath(extract_to)
    for member in zf.namelist():
        member_path = os.path.realpath(os.path.join(target, member))
        if not member_path.startswith(target + os.sep) and member_path != target:
            raise ValueError(f"Path traversal detectado: {member}")
    zf.extractall(extract_to)


def _extract_archive(archive_path, extract_to):
    """Extrai ZIP, RAR ou TAR e retorna o diretorio com arquivos .php."""
    lower = archive_path.lower()
    basename = os.path.basename(archive_path)

    if lower.endswith('.zip'):
        log.info(f'Extraindo ZIP: {basename}')
        with zipfile.ZipFile(archive_path, 'r') as zf:
            _safe_zip_extract(zf, extract_to)

    elif lower.endswith('.rar'):
        log.info(f'Extraindo RAR: {basename}')
        subprocess.run(
            ['unrar', 'x', '-o+', archive_path, extract_to],
            check=True, capture_output=True,
        )

    elif lower.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2')):
        log.info(f'Extraindo TAR: {basename}')
        with tarfile.open(archive_path, 'r:*') as tf:
            tf.extractall(extract_to, filter='data')

    else:
        raise ValueError(f"Formato nao suportado: {basename}")

    # Encontrar diretorio com PHPs
    for dirpath, _, filenames in os.walk(extract_to):
        php_count = sum(1 for f in filenames if f.endswith('.php'))
        if php_count > 0:
            log.info(f'Encontrados {php_count} arquivos PHP em {os.path.relpath(dirpath, extract_to)}')
            return dirpath

    log.warning(f'Nenhum arquivo PHP encontrado no arquivo {basename}')
    return extract_to


def _create_tar(source_dir, tar_path):
    """Compacta diretorio de saida em TAR.GZ."""
    file_count = 0
    with tarfile.open(tar_path, 'w:gz') as tf:
        for dirpath, _, filenames in os.walk(source_dir):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                tf.add(full, arcname=os.path.relpath(full, source_dir))
                file_count += 1
    size_kb = os.path.getsize(tar_path) / 1024
    log.info(f'TAR criado: {file_count} arquivos, {size_kb:.1f} KB')


def _detect_version(input_dir):
    """Detecta versao do software a partir dos arquivos PHP."""
    import re as _re
    version_patterns = [
        _re.compile(r"""\$version\s*=\s*['"]([0-9]+\.[0-9]+(?:\.[0-9]+)?)['"]""", _re.IGNORECASE),
        _re.compile(r"""@version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)"""),
        _re.compile(r"""Version:\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)"""),
    ]
    for dirpath, _, filenames in os.walk(input_dir):
        for fname in sorted(filenames):
            if not fname.endswith('.php'):
                continue
            filepath = os.path.join(dirpath, fname)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(8192)
                for pattern in version_patterns:
                    m = pattern.search(content)
                    if m:
                        return m.group(1)
            except Exception:
                continue
    return '1.0.0'


def _create_meta_file(meta_path, input_dir):
    """Cria arquivo meta com informacoes do language pack."""
    version = _detect_version(input_dir)
    content = (
        f'ISO: pt_br\n'
        f'Language: Portuguese\n'
        f'Charset: UTF-8\n'
        f'Version: {version}\n'
    )
    with open(meta_path, 'w', encoding='utf-8') as f:
        f.write(content)
    log.info(f'Meta criado: Version={version}')


# ============================================================================
# Contagem de strings
# ============================================================================

def _count_strings(file_path):
    """Conta $msg_arr em um arquivo PHP."""
    count = 0
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                s = line.rstrip('\n')
                if trans_engine.SINGLE_QUOTE_RE.match(s) or \
                   trans_engine.DOUBLE_QUOTE_RE.match(s):
                    count += 1
    except Exception:
        pass
    return count


# ============================================================================
# Traducao de arquivo individual (com progresso)
# ============================================================================

def _translate_file(src_path, dst_path, delay, cache, job, socketio=None):
    """
    Traduz um arquivo PHP linha a linha.
    Usa as funcoes do translate.py mas emite progresso no job.
    """
    rel = os.path.relpath(src_path, job.input_dir)

    try:
        with open(src_path, 'r', encoding='utf-8') as f:
            src_lines = f.readlines()
    except Exception as e:
        log.error(f'[{job.job_id}] Erro ao ler {rel}: {e}')
        job.errors.append(f"Erro leitura: {rel}: {e}")
        return 0

    total_lines = len(src_lines)

    # Resume
    start_line = 0
    if os.path.exists(dst_path):
        try:
            with open(dst_path, 'r', encoding='utf-8') as f:
                start_line = len(f.readlines())
            if start_line >= total_lines:
                log.debug(f'[{job.job_id}] Pulando (completo): {rel}')
                return 0
            log.info(f'[{job.job_id}] Resumindo {rel} da linha {start_line + 1}/{total_lines}')
        except Exception:
            pass
    else:
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    mode = 'a' if start_line > 0 else 'w'
    count = 0
    cached_count = 0
    fresh_count = 0
    failed_count = 0

    try:
        with open(dst_path, mode, encoding='utf-8') as out:
            for i in range(start_line, total_lines):
                if job._cancel_flag:
                    log.info(f'[{job.job_id}] Cancelado durante {rel} (linha {i})')
                    return count

                line = src_lines[i]
                stripped = line.rstrip('\n')

                m = trans_engine.SINGLE_QUOTE_RE.match(stripped)
                qc = "'"
                if not m:
                    m = trans_engine.DOUBLE_QUOTE_RE.match(stripped)
                    qc = '"'

                if m:
                    prefix, raw_value, suffix = m.group(1), m.group(2), m.group(3)

                    text = trans_engine.prepare_for_translation(raw_value, qc)
                    text, ph_map = trans_engine.protect_placeholders(text)

                    # Cache SQLite global: popula cache local antes de chamar translate-shell
                    if text not in cache:
                        db_result = get_cached_translation_db(text)
                        if db_result:
                            cache[text] = db_result

                    was_cached = text in cache
                    translated = trans_engine.get_cached_translation(text, delay, cache)

                    # Persiste no SQLite se foi uma nova traducao (e nao falhou)
                    if not was_cached and text.strip() != translated.strip():
                        save_cached_translation_db(text, translated)

                    # Contadores de diagnostico
                    if was_cached:
                        cached_count += 1
                    elif text.strip() != translated.strip():
                        fresh_count += 1
                    else:
                        failed_count += 1

                    translated = trans_engine.restore_placeholders(translated, ph_map)
                    translated = trans_engine.re_escape(translated, qc)

                    out.write(prefix + translated + suffix + '\n')
                    count += 1
                    job.translated_strings += 1

                    if socketio and job.total_strings > 0:
                        job.progress = int((job.translated_strings / job.total_strings) * 100)
                        socketio.emit('translation_progress', job.to_dict(), room=job.job_id)

                    time.sleep(delay)
                else:
                    out.write(line)

                out.flush()
    except Exception as e:
        log.error(f'[{job.job_id}] Erro em {rel} linha {i}: {e}')
        job.errors.append(f"Erro: {rel}: {e}")

    log.info(f'[{job.job_id}] {rel}: {count} strings '
             f'({cached_count} cache, {fresh_count} traduzidas, {failed_count} falhas)')
    return count


# ============================================================================
# Runner — executa traducao em background thread
# ============================================================================

def _run(job, socketio):
    """Thread principal de traducao."""
    log.info(f'[{job.job_id}] Iniciando traducao (delay={job.delay}s)')
    job.status = 'running'
    job.started_at = datetime.now().isoformat()
    socketio.emit('translation_progress', job.to_dict(), room=job.job_id)

    try:
        log.debug(f'[{job.job_id}] Verificando translate-shell...')
        trans_engine.ensure_trans()
        trans_path = shutil.which('trans')
        log.info(f'[{job.job_id}] trans binary: {trans_path or "NAO ENCONTRADO"}')

        # Coletar arquivos PHP
        tasks = []
        for dirpath, dirnames, filenames in os.walk(job.input_dir):
            dirnames.sort()
            for fname in sorted(filenames):
                if not fname.endswith('.php'):
                    continue
                src = os.path.join(dirpath, fname)
                rel = os.path.relpath(src, job.input_dir)
                dst = os.path.join(job.output_dir, rel)
                tasks.append((src, dst, rel, _count_strings(src)))

        job.total_files = len(tasks)
        job.total_strings = sum(t[3] for t in tasks)
        log.info(f'[{job.job_id}] {job.total_files} arquivos, {job.total_strings} strings')
        socketio.emit('translation_progress', job.to_dict(), room=job.job_id)

        if not tasks:
            log.error(f'[{job.job_id}] Nenhum arquivo PHP encontrado')
            job.errors.append("Nenhum arquivo PHP encontrado no arquivo enviado")
            job.status = 'failed'
            job.finished_at = datetime.now().isoformat()
            socketio.emit('translation_error', job.to_dict(), room=job.job_id)
            return

        cache = {}

        for idx, (src, dst, rel, _) in enumerate(tasks):
            if job._cancel_flag:
                job.status = 'cancelled'
                job.finished_at = datetime.now().isoformat()
                log.info(f'[{job.job_id}] Cancelado pelo usuario ({idx}/{job.total_files} arquivos)')
                socketio.emit('translation_progress', job.to_dict(), room=job.job_id)
                return

            job.current_file = rel
            job.files_done = idx
            log.info(f'[{job.job_id}] [{idx + 1}/{job.total_files}] Traduzindo: {rel}')
            socketio.emit('translation_progress', job.to_dict(), room=job.job_id)

            _translate_file(src, dst, job.delay, cache, job, socketio)

        # Finalizar
        job.files_done = job.total_files
        job.progress = 100
        job.current_file = ''

        # Validar
        log.info(f'[{job.job_id}] Validando traducao...')
        try:
            stats, issues = trans_engine.validate_translation(job.input_dir, job.output_dir)
            job.validation = {'stats': stats, 'issues': issues[:20]}
            log.info(f'[{job.job_id}] Validacao: {stats["success"]} OK, '
                     f'{stats["untranslated"]} nao traduzidas, '
                     f'{stats["missing_placeholders"]} placeholders perdidos')
        except Exception as e:
            log.error(f'[{job.job_id}] Erro na validacao: {e}')
            job.validation = {'error': str(e)}

        # Montar estrutura language/meta + language/pt_br/
        job_dir = os.path.join(JOBS_FOLDER, job.job_id)
        package_dir = os.path.join(job_dir, 'package')
        lang_dir = os.path.join(package_dir, 'language')
        pt_br_dir = os.path.join(lang_dir, 'pt_br')

        os.makedirs(lang_dir, exist_ok=True)
        shutil.copytree(job.output_dir, pt_br_dir, dirs_exist_ok=True)

        log.info(f'[{job.job_id}] Criando arquivo meta...')
        _create_meta_file(os.path.join(lang_dir, 'meta'), job.input_dir)

        # TAR de saida
        tar_path = os.path.join(job_dir, 'output.tar.gz')
        log.info(f'[{job.job_id}] Criando TAR de saida...')
        _create_tar(package_dir, tar_path)
        job.output_tar = tar_path

        # Limpar diretorio temporario de empacotamento
        shutil.rmtree(package_dir, ignore_errors=True)

        job.status = 'completed'
        job.finished_at = datetime.now().isoformat()

        elapsed = (datetime.fromisoformat(job.finished_at) -
                   datetime.fromisoformat(job.started_at)).total_seconds()
        log.info(f'[{job.job_id}] CONCLUIDO em {elapsed:.1f}s — '
                 f'{job.translated_strings} strings, {len(cache)} unicas (cache)')

        socketio.emit('translation_complete', job.to_dict(), room=job.job_id)

    except Exception as e:
        job.status = 'failed'
        job.finished_at = datetime.now().isoformat()
        job.errors.append(f"Erro fatal: {str(e)}")
        log.error(f'[{job.job_id}] FALHA FATAL: {e}', exc_info=True)
        socketio.emit('translation_error', job.to_dict(), room=job.job_id)


# ============================================================================
# API publica do servico
# ============================================================================

def start_translation(archive_path, delay, socketio, user_email=''):
    """Inicia novo job. Retorna job_id."""
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(JOBS_FOLDER, job_id)
    input_dir = os.path.join(job_dir, 'input')
    output_dir = os.path.join(job_dir, 'output')

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    log.info(f'[{job_id}] Extraindo arquivo...')
    php_dir = _extract_archive(archive_path, input_dir)

    job = TranslationJob(job_id, php_dir, output_dir, delay, user_email)
    _put(job)

    threading.Thread(target=_run, args=(job, socketio), daemon=True).start()
    log.info(f'[{job_id}] Thread de traducao iniciada')
    return job_id


def get_job(job_id):
    return _get(job_id)


def delete_job(job_id):
    job = _pop(job_id)
    if job:
        job_dir = os.path.join(JOBS_FOLDER, job_id)
        shutil.rmtree(job_dir, ignore_errors=True)
        log.info(f'[{job_id}] Job removido e arquivos limpos')
        return True
    return False


def list_jobs(user_email=None):
    with _jobs_lock:
        jobs = list(_jobs.values())
    if user_email:
        jobs = [j for j in jobs if j.user_email == user_email]
    return [j.to_dict() for j in jobs]


def cleanup_old_jobs(max_age_hours=24):
    """Remove jobs finalizados com mais de X horas."""
    now = datetime.now()
    to_delete = []
    with _jobs_lock:
        for jid, job in _jobs.items():
            created = datetime.fromisoformat(job.created_at)
            if (now - created).total_seconds() / 3600 > max_age_hours \
               and job.status in ('completed', 'failed', 'cancelled'):
                to_delete.append(jid)
    for jid in to_delete:
        delete_job(jid)
    if to_delete:
        log.info(f'Cleanup: {len(to_delete)} jobs antigos removidos')
