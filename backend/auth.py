"""Modulo de autenticacao — OTP por e-mail + SQLite (usuarios + cache de traducoes + jobs)."""

import json
import os
import random
import sqlite3
import smtplib
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import (
    DB_PATH, OTP_EXPIRY_MINUTES, OTP_MAX_ATTEMPTS,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, log,
)


# ============================================================================
# SQLite
# ============================================================================

@contextmanager
def _db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Cria tabelas SQLite se nao existirem."""
    with _db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    UNIQUE NOT NULL,
                created_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS translation_cache (
                source_text      TEXT PRIMARY KEY,
                translated_text  TEXT NOT NULL,
                hit_count        INTEGER DEFAULT 1,
                created_at       TEXT    NOT NULL,
                last_used_at     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id              TEXT PRIMARY KEY,
                user_email          TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'pending',
                progress            INTEGER DEFAULT 0,
                current_file        TEXT DEFAULT '',
                total_files         INTEGER DEFAULT 0,
                files_done          INTEGER DEFAULT 0,
                total_strings       INTEGER DEFAULT 0,
                translated_strings  INTEGER DEFAULT 0,
                errors              TEXT DEFAULT '[]',
                validation          TEXT,
                output_zip          TEXT,
                created_at          TEXT NOT NULL,
                started_at          TEXT,
                finished_at         TEXT
            );
        """)
    log.info('[AUTH] Banco de dados inicializado')


def get_or_create_user(email):
    """Retorna usuario existente ou cria um novo (cadastro automatico)."""
    email = email.strip().lower()
    now = datetime.now().isoformat()
    with _db_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (email, created_at) VALUES (?, ?)",
            (email, now),
        )
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return dict(row)


# ============================================================================
# Cache global de traducoes (persistente entre jobs e usuarios)
# ============================================================================

_db_lock = threading.Lock()


def get_cached_translation_db(source_text):
    """Busca traducao no cache SQLite. Retorna string ou None."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                row = conn.execute(
                    "SELECT translated_text FROM translation_cache WHERE source_text = ?",
                    (source_text,),
                ).fetchone()
                if row:
                    now = datetime.now().isoformat()
                    conn.execute(
                        "UPDATE translation_cache "
                        "SET hit_count = hit_count + 1, last_used_at = ? "
                        "WHERE source_text = ?",
                        (now, source_text),
                    )
                    return row['translated_text']
    except Exception as e:
        log.debug(f'[CACHE] Erro ao buscar cache: {e}')
    return None


def save_cached_translation_db(source_text, translated_text):
    """Salva traducao no cache SQLite (INSERT OR UPDATE)."""
    now = datetime.now().isoformat()
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO translation_cache
                        (source_text, translated_text, hit_count, created_at, last_used_at)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(source_text) DO UPDATE SET
                        hit_count    = hit_count + 1,
                        last_used_at = excluded.last_used_at
                    """,
                    (source_text, translated_text, now, now),
                )
    except Exception as e:
        log.debug(f'[CACHE] Erro ao salvar cache: {e}')


# ============================================================================
# Persistencia de jobs (SQLite)
# ============================================================================

def save_job_db(job_dict):
    """Salva ou atualiza um job no SQLite."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs
                        (job_id, user_email, status, progress, current_file,
                         total_files, files_done, total_strings, translated_strings,
                         errors, validation, output_zip, created_at, started_at, finished_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status             = excluded.status,
                        progress           = excluded.progress,
                        current_file       = excluded.current_file,
                        total_files        = excluded.total_files,
                        files_done         = excluded.files_done,
                        total_strings      = excluded.total_strings,
                        translated_strings = excluded.translated_strings,
                        errors             = excluded.errors,
                        validation         = excluded.validation,
                        output_zip         = excluded.output_zip,
                        started_at         = excluded.started_at,
                        finished_at        = excluded.finished_at
                    """,
                    (
                        job_dict['job_id'],
                        job_dict.get('user_email', ''),
                        job_dict['status'],
                        job_dict.get('progress', 0),
                        job_dict.get('current_file', ''),
                        job_dict.get('total_files', 0),
                        job_dict.get('files_done', 0),
                        job_dict.get('total_strings', 0),
                        job_dict.get('translated_strings', 0),
                        json.dumps(job_dict.get('errors', [])),
                        json.dumps(job_dict.get('validation')) if job_dict.get('validation') else None,
                        job_dict.get('output_zip'),
                        job_dict['created_at'],
                        job_dict.get('started_at'),
                        job_dict.get('finished_at'),
                    ),
                )
    except Exception as e:
        log.error(f'[DB] Erro ao salvar job {job_dict.get("job_id")}: {e}')


def load_jobs_db(user_email=None):
    """Carrega jobs do SQLite. Filtra por user_email se fornecido."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                if user_email:
                    rows = conn.execute(
                        "SELECT * FROM jobs WHERE user_email = ? ORDER BY created_at DESC",
                        (user_email,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM jobs ORDER BY created_at DESC",
                    ).fetchall()
                return [_row_to_job_dict(r) for r in rows]
    except Exception as e:
        log.error(f'[DB] Erro ao carregar jobs: {e}')
        return []


def load_job_db(job_id):
    """Carrega um unico job do SQLite."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if row:
                    return _row_to_job_dict(row)
    except Exception as e:
        log.error(f'[DB] Erro ao carregar job {job_id}: {e}')
    return None


def delete_job_db(job_id):
    """Remove um job do SQLite."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    except Exception as e:
        log.error(f'[DB] Erro ao deletar job {job_id}: {e}')


def cleanup_old_jobs_db(max_age_hours=24):
    """Remove jobs finalizados com mais de X horas do SQLite."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute(
                    """
                    DELETE FROM jobs
                    WHERE status IN ('completed', 'failed', 'cancelled')
                    AND datetime(created_at) < datetime('now', ? || ' hours')
                    """,
                    (f'-{max_age_hours}',),
                )
    except Exception as e:
        log.error(f'[DB] Erro no cleanup de jobs: {e}')


def _row_to_job_dict(row):
    """Converte uma linha SQLite em dicionario de job."""
    d = dict(row)
    try:
        d['errors'] = json.loads(d.get('errors') or '[]')
    except (json.JSONDecodeError, TypeError):
        d['errors'] = []
    try:
        val = d.get('validation')
        d['validation'] = json.loads(val) if val else None
    except (json.JSONDecodeError, TypeError):
        d['validation'] = None
    d['has_output'] = d.get('output_zip') is not None
    return d


# ============================================================================
# OTP em memoria
# ============================================================================

_otps = {}           # {email: {code, expires_at, attempts, sent_at}}
_otp_lock = threading.Lock()

OTP_RESEND_SECONDS = 60  # Rate limit de reenvio por e-mail


def generate_otp(email):
    """
    Gera codigo OTP de 6 digitos para o e-mail.
    Retorna (code, 0) se gerado com sucesso.
    Retorna (None, remaining_seconds) se rate limit ativo.
    """
    email = email.strip().lower()
    now = time.time()

    with _otp_lock:
        existing = _otps.get(email)
        if existing and now - existing['sent_at'] < OTP_RESEND_SECONDS:
            remaining = int(OTP_RESEND_SECONDS - (now - existing['sent_at']))
            return None, remaining

        code = f"{random.randint(0, 999999):06d}"
        _otps[email] = {
            'code': code,
            'expires_at': now + OTP_EXPIRY_MINUTES * 60,
            'attempts': 0,
            'sent_at': now,
        }
        return code, 0


def verify_otp(email, code):
    """
    Verifica codigo OTP.
    Retorna (True, None) se valido.
    Retorna (False, 'motivo') se invalido.
    """
    email = email.strip().lower()
    now = time.time()

    with _otp_lock:
        entry = _otps.get(email)

        if not entry:
            return False, 'Nenhum codigo solicitado para este e-mail.'

        if now > entry['expires_at']:
            del _otps[email]
            return False, 'Codigo expirado. Solicite um novo.'

        entry['attempts'] += 1

        if entry['attempts'] > OTP_MAX_ATTEMPTS:
            del _otps[email]
            return False, 'Muitas tentativas. Solicite um novo codigo.'

        if entry['code'] != code.strip():
            remaining = OTP_MAX_ATTEMPTS - entry['attempts']
            if remaining <= 0:
                del _otps[email]
                return False, 'Codigo incorreto. Solicite um novo codigo.'
            return False, f'Codigo incorreto. {remaining} tentativa(s) restante(s).'

        del _otps[email]
        return True, None


# ============================================================================
# Envio de e-mail via smtplib
# ============================================================================

def send_otp_email(email, code):
    """Envia e-mail com codigo OTP. Se SMTP nao configurado, imprime no log."""
    if not SMTP_USER or not SMTP_PASS:
        log.info(f'[AUTH] OTP para {email}: {code}  (SMTP nao configurado — apenas log)')
        return

    subject = f'Seu codigo de acesso: {code}'

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#111827;font-family:system-ui,-apple-system,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 16px">
        <table width="440" cellpadding="0" cellspacing="0"
               style="background:#1f2937;border-radius:12px;border:1px solid #374151">
          <tr>
            <td style="padding:32px 32px 0">
              <div style="display:inline-flex;align-items:center;gap:10px">
                <div style="width:36px;height:36px;background:#2563eb;border-radius:8px;
                            text-align:center;line-height:36px;font-size:18px;
                            font-weight:bold;color:#fff">T</div>
                <span style="font-size:18px;font-weight:600;color:#fff">Trans-Script</span>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px 8px">
              <p style="margin:0;font-size:22px;font-weight:600;color:#fff">
                Seu codigo de acesso
              </p>
              <p style="margin:8px 0 0;font-size:14px;color:#9ca3af">
                Use o codigo abaixo para entrar.
                Valido por {OTP_EXPIRY_MINUTES} minutos.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px">
              <div style="background:#111827;border:1px solid #374151;border-radius:8px;
                          text-align:center;padding:20px 16px">
                <span style="font-size:40px;font-weight:700;letter-spacing:14px;
                             color:#fff;font-family:monospace">{code}</span>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 32px">
              <p style="margin:0;font-size:12px;color:#6b7280">
                Se voce nao solicitou este codigo, ignore este e-mail.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = email
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        # Porta 465 = SSL implicito (SMTPS); demais = STARTTLS
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, [email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, [email], msg.as_string())
        log.info(f'[AUTH] OTP enviado para {email}')
    except Exception as e:
        log.error(f'[AUTH] Erro ao enviar OTP para {email}: {e}')
        raise RuntimeError(f'Erro ao enviar e-mail: {e}')
