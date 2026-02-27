"""Modulo de autenticacao — Senha + OTP por e-mail + SQLite (usuarios + cache de traducoes)."""

import os
import random
import re
import sqlite3
import smtplib
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from werkzeug.security import generate_password_hash, check_password_hash

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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT,
                created_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS translation_cache (
                source_text      TEXT PRIMARY KEY,
                translated_text  TEXT NOT NULL,
                hit_count        INTEGER DEFAULT 1,
                created_at       TEXT    NOT NULL,
                last_used_at     TEXT    NOT NULL
            );
        """)
        # Migracao: adicionar coluna password_hash se nao existir
        try:
            conn.execute("SELECT password_hash FROM users LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            log.info('[AUTH] Coluna password_hash adicionada (migracao)')
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


def list_all_users():
    """Lista todos os usuarios (para painel admin)."""
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, is_admin, created_at FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_system_stats():
    """Retorna estatisticas do banco (para painel admin)."""
    with _db_conn() as conn:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        cache_count = conn.execute("SELECT COUNT(*) FROM translation_cache").fetchone()[0]
        cache_hits = conn.execute("SELECT SUM(hit_count) FROM translation_cache").fetchone()[0] or 0
    return {
        'users': user_count,
        'admins': admin_count,
        'cache_entries': cache_count,
        'cache_total_hits': cache_hits,
    }


def get_user_by_id(user_id):
    """Busca usuario por ID."""
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT id, email, is_admin, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


# ============================================================================
# Autenticacao por senha
# ============================================================================

# Requisitos minimos da senha
_MIN_PASSWORD_LENGTH = 6


def _validate_password(password):
    """Valida requisitos minimos da senha. Retorna (ok, mensagem)."""
    if not password or len(password) < _MIN_PASSWORD_LENGTH:
        return False, f'Senha deve ter pelo menos {_MIN_PASSWORD_LENGTH} caracteres.'
    return True, None


def register_user(email, password):
    """
    Registra usuario com e-mail + senha.
    Retorna (user_dict, None) se sucesso, (None, erro) se falha.
    Usa scrypt (werkzeug default) — seguro e resistente a brute-force.
    """
    email = email.strip().lower()
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return None, 'E-mail invalido.'

    ok, msg = _validate_password(password)
    if not ok:
        return None, msg

    now = datetime.now().isoformat()
    hashed = generate_password_hash(password)

    with _db_conn() as conn:
        existing = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing:
            if existing['password_hash']:
                return None, 'E-mail ja cadastrado. Faca login.'
            # Usuario criado via OTP sem senha — definir senha agora
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE email = ?",
                (hashed, email),
            )
            row = conn.execute(
                "SELECT id, email, created_at FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            log.info(f'[AUTH] Senha definida para usuario existente: {email}')
            return dict(row), None

        conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, hashed, now),
        )
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        log.info(f'[AUTH] Novo usuario registrado: {email}')
        return dict(row), None


def login_user(email, password):
    """
    Autentica usuario com e-mail + senha.
    Retorna (user_dict, None) se sucesso, (None, erro) se falha.
    Usa constant-time comparison (check_password_hash) para evitar timing attacks.
    """
    email = email.strip().lower()
    if not email or not password:
        return None, 'E-mail e senha sao obrigatorios.'

    with _db_conn() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not row:
        # Gastar tempo com hash para evitar timing attack (user enumeration)
        check_password_hash(
            'scrypt:32768:8:1$dummy$0000000000000000000000000000000000000000000000000000000000000000',
            password,
        )
        return None, 'E-mail ou senha incorretos.'

    if not row['password_hash']:
        return None, 'Conta sem senha. Use o codigo por e-mail ou cadastre uma senha.'

    if not check_password_hash(row['password_hash'], password):
        return None, 'E-mail ou senha incorretos.'

    user = {'id': row['id'], 'email': row['email'], 'created_at': row['created_at']}
    log.info(f'[AUTH] Login com senha: {email}')
    return user, None


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


def clear_untranslated_cache():
    """Remove entradas do cache onde a traducao e igual ao original."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                deleted = conn.execute(
                    "DELETE FROM translation_cache "
                    "WHERE LOWER(TRIM(source_text)) = LOWER(TRIM(translated_text))"
                ).rowcount
                log.info(f'[CACHE] Limpeza: {deleted} traducoes falhadas removidas do cache')
                return deleted
    except Exception as e:
        log.error(f'[CACHE] Erro ao limpar cache: {e}')
        return 0


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
                <span style="font-size:18px;font-weight:600;color:#fff">Traducao</span>
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
