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
from backend.engine import get_engine

BATCH_SIZE = 50


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
        self.output_zip = None

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
            'has_output': self.output_zip is not None,
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


def _create_zip(source_dir, zip_path):
    """Compacta diretorio de saida em ZIP."""
    file_count = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, filenames in os.walk(source_dir):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                zf.write(full, os.path.relpath(full, source_dir))
                file_count += 1
    size_kb = os.path.getsize(zip_path) / 1024
    log.info(f'ZIP criado: {file_count} arquivos, {size_kb:.1f} KB')


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

def _translate_file(src_path, dst_path, delay, job, socketio=None):
    """
    Traduz um arquivo PHP usando batch translation (2-pass).
    Pass 1: coleta strings traduziveis. Pass 2: traduz em lotes.
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

    # --- Pass 1: coletar strings traduziveis ---
    entries = []  # (idx_in_output, text_prepared, ph_map, prefix, suffix, qc)
    output_lines = []

    for i in range(start_line, total_lines):
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
            entries.append((len(output_lines), text, ph_map, prefix, suffix, qc))
            output_lines.append(None)  # placeholder, sera preenchido no pass 2
        else:
            output_lines.append(line)

    # --- Pass 2: traduzir em batches ---
    engine = get_engine()

    try:
        for batch_start in range(0, len(entries), BATCH_SIZE):
            if job._cancel_flag:
                log.info(f'[{job.job_id}] Cancelado durante {rel} (batch {batch_start // BATCH_SIZE})')
                break

            batch_entries = entries[batch_start:batch_start + BATCH_SIZE]
            batch_texts = [e[1] for e in batch_entries]

            translations = engine.translate_batch(batch_texts)

            for entry, translated in zip(batch_entries, translations):
                idx, _text, ph_map, prefix, suffix, qc = entry
                translated = trans_engine.restore_placeholders(translated, ph_map)
                translated = trans_engine.re_escape(translated, qc)
                output_lines[idx] = prefix + translated + suffix + '\n'
                count += 1
                job.translated_strings += 1

            # Progresso via WebSocket a cada batch
            if socketio and job.total_strings > 0:
                job.progress = int((job.translated_strings / job.total_strings) * 100)
                socketio.emit('translation_progress', job.to_dict(), room=job.job_id)

            time.sleep(delay)

    except Exception as e:
        log.error(f'[{job.job_id}] Erro em {rel} batch: {e}')
        job.errors.append(f"Erro: {rel}: {e}")

    # --- Pass 3: escrever arquivo ---
    try:
        with open(dst_path, mode, encoding='utf-8') as out:
            for line in output_lines:
                if line is not None:
                    out.write(line)
            out.flush()
    except Exception as e:
        log.error(f'[{job.job_id}] Erro ao escrever {rel}: {e}')
        job.errors.append(f"Erro escrita: {rel}: {e}")

    log.info(f'[{job.job_id}] {rel}: {count} strings traduzidas (batch)')
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
        log.debug(f'[{job.job_id}] Inicializando engine de traducao...')
        get_engine()  # Garante que a engine esta inicializada

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

            _translate_file(src, dst, job.delay, job, socketio)

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

        # ZIP de saida
        zip_path = os.path.join(JOBS_FOLDER, job.job_id, 'output.zip')
        log.info(f'[{job.job_id}] Criando ZIP de saida...')
        _create_zip(job.output_dir, zip_path)
        job.output_zip = zip_path

        job.status = 'completed'
        job.finished_at = datetime.now().isoformat()

        elapsed = (datetime.fromisoformat(job.finished_at) -
                   datetime.fromisoformat(job.started_at)).total_seconds()
        cache_stats = get_engine().cache.get_stats()
        log.info(f'[{job.job_id}] CONCLUIDO em {elapsed:.1f}s — '
                 f'{job.translated_strings} strings, '
                 f'{cache_stats["l1_size"]} unicas (cache L1, '
                 f'hit rate {cache_stats["hit_rate_total"]})')

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
    """Inicia novo job a partir de arquivo compactado. Retorna job_id."""
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


def start_translation_raw(php_dir, delay, socketio, user_email=''):
    """Inicia novo job a partir de arquivos PHP avulsos (sem extracao). Retorna job_id."""
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(JOBS_FOLDER, job_id)
    input_dir = os.path.join(job_dir, 'input')
    output_dir = os.path.join(job_dir, 'output')

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Mover arquivos PHP para o diretorio do job
    for dirpath, dirnames, filenames in os.walk(php_dir):
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(src, php_dir)
            dst = os.path.join(input_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)

    # Limpar diretorio temporario original
    shutil.rmtree(php_dir, ignore_errors=True)

    log.info(f'[{job_id}] Arquivos PHP movidos para job (sem extracao)')

    job = TranslationJob(job_id, input_dir, output_dir, delay, user_email)
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
