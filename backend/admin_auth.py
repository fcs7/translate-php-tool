"""
Modulo de sessao administrativa com criptografia forte.

Seguranca:
  - Chave derivada via HKDF-SHA256 (256-bit) a partir do SECRET_KEY
  - Tokens de sessao: secrets.token_urlsafe(48) → 384 bits de entropia
  - Tokens armazenados como hash SHA-256 (nunca em texto puro)
  - Payload da sessao criptografado com AES-256-GCM (nonce 96-bit unico)
  - HMAC-SHA256 para verificacao de integridade do token
  - Sessoes vinculadas a IP e com expiracao curta (configuravel)
"""

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextlib import contextmanager
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac

from backend.config import DB_PATH, SECRET_KEY, ADMIN_SESSION_EXPIRY_HOURS, log


# ============================================================================
# Derivacao de chaves (HKDF-SHA256, 256-bit)
# ============================================================================

def _derive_key(purpose: bytes) -> bytes:
    """
    Deriva uma chave de 256 bits a partir do SECRET_KEY usando HKDF-SHA256.
    Cada 'purpose' gera uma chave diferente (separacao de dominio).
    Salt derivado do SECRET_KEY para consistencia entre reinicializacoes.
    """
    # Salt determinístico derivado do SECRET_KEY (evita salt=None zero-length)
    salt = hashlib.sha256(b'admin-hkdf-salt:' + SECRET_KEY.encode('utf-8')).digest()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        info=purpose,
    )
    return hkdf.derive(SECRET_KEY.encode('utf-8'))


# Chaves derivadas para diferentes propositos (256-bit cada)
_ENCRYPTION_KEY = _derive_key(b'admin-session-encryption-v1')
_SIGNING_KEY = _derive_key(b'admin-session-signing-v1')


# ============================================================================
# Criptografia AES-256-GCM
# ============================================================================

def encrypt_payload(data: dict) -> str:
    """
    Criptografa payload JSON com AES-256-GCM.
    Retorna string base64url: nonce(12) || ciphertext || tag(16)
    Chave: 256 bits (derivada via HKDF)
    """
    plaintext = json.dumps(data, separators=(',', ':')).encode('utf-8')
    nonce = os.urandom(12)  # 96-bit nonce (recomendado para GCM)
    aesgcm = AESGCM(_ENCRYPTION_KEY)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return urlsafe_b64encode(nonce + ciphertext).decode('ascii')


def decrypt_payload(token: str) -> dict | None:
    """
    Descriptografa payload AES-256-GCM.
    Retorna dict ou None se falhar (token adulterado/invalido).
    """
    try:
        raw = urlsafe_b64decode(token)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(_ENCRYPTION_KEY)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)
    except Exception:
        return None


# ============================================================================
# HMAC-SHA256 para assinatura de tokens
# ============================================================================

def sign_token(token: str) -> str:
    """Assina token com HMAC-SHA256 (256-bit key). Retorna hex."""
    h = crypto_hmac.HMAC(_SIGNING_KEY, hashes.SHA256())
    h.update(token.encode('utf-8'))
    return h.finalize().hex()


def verify_signature(token: str, signature: str) -> bool:
    """Verifica assinatura HMAC-SHA256."""
    try:
        h = crypto_hmac.HMAC(_SIGNING_KEY, hashes.SHA256())
        h.update(token.encode('utf-8'))
        h.verify(bytes.fromhex(signature))
        return True
    except Exception:
        return False


# ============================================================================
# Hash de token para armazenamento (SHA-256)
# ============================================================================

def _hash_token(token: str) -> str:
    """SHA-256 do token para armazenamento seguro (nunca guardar raw)."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


# ============================================================================
# SQLite — tabelas admin
# ============================================================================

_admin_lock = threading.Lock()


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


def init_admin_db():
    """Cria tabelas de admin se nao existirem e migra coluna is_admin."""
    with _admin_lock:
        with _db_conn() as conn:
            # Tabela de sessoes admin (server-side)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token_hash   TEXT PRIMARY KEY,
                    user_email   TEXT NOT NULL,
                    ip_address   TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    expires_at   REAL NOT NULL,
                    revoked      INTEGER DEFAULT 0
                )
            """)

            # Adicionar coluna is_admin na tabela users (migration segura)
            cols = [row['name'] for row in conn.execute("PRAGMA table_info(users)")]
            if 'is_admin' not in cols:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"
                )
                log.info('[ADMIN] Coluna is_admin adicionada a tabela users')

    log.info('[ADMIN] Tabelas admin inicializadas')


# ============================================================================
# Gestao de admins
# ============================================================================

def set_admin(email: str, is_admin: bool = True):
    """Promove ou rebaixa usuario a admin."""
    email = email.strip().lower()
    with _admin_lock:
        with _db_conn() as conn:
            conn.execute(
                "UPDATE users SET is_admin = ? WHERE email = ?",
                (1 if is_admin else 0, email),
            )
    action = 'promovido a admin' if is_admin else 'rebaixado de admin'
    log.info(f'[ADMIN] {email} {action}')


def is_admin(email: str) -> bool:
    """Verifica se usuario e admin."""
    email = email.strip().lower()
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT is_admin FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        return bool(row and row['is_admin'])


def list_admins() -> list[dict]:
    """Lista todos os admins."""
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, created_at FROM users WHERE is_admin = 1"
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================================
# Sessoes admin (server-side, criptografadas)
# ============================================================================

def create_admin_session(email: str, ip: str) -> str | None:
    """
    Cria sessao admin segura. Retorna token_composto ou None se nao for admin.

    Token composto = token_raw + '.' + hmac_signature
    - token_raw: secrets.token_urlsafe(48) → 384 bits de entropia
    - Armazenado como SHA-256 hash no banco
    - Dados da sessao criptografados com AES-256-GCM
    """
    if not is_admin(email):
        return None

    token_raw = secrets.token_urlsafe(48)  # 384 bits
    token_hash = _hash_token(token_raw)
    signature = sign_token(token_raw)

    # Dados criptografados da sessao
    session_data = {
        'email': email,
        'ip': ip,
        'iat': time.time(),
        'jti': secrets.token_hex(16),  # ID unico da sessao (128 bits)
    }
    encrypted = encrypt_payload(session_data)

    now = datetime.now().isoformat()
    expires_at = time.time() + (ADMIN_SESSION_EXPIRY_HOURS * 3600)

    with _admin_lock:
        with _db_conn() as conn:
            # Revogar sessoes anteriores do mesmo usuario
            conn.execute(
                "UPDATE admin_sessions SET revoked = 1 WHERE user_email = ? AND revoked = 0",
                (email,),
            )
            # Inserir nova sessao
            conn.execute(
                """INSERT INTO admin_sessions
                   (token_hash, user_email, ip_address, encrypted_data, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (token_hash, email, ip, encrypted, now, expires_at),
            )

    log.info(f'[ADMIN] Sessao criada para {email} (IP: {ip}, expira em {ADMIN_SESSION_EXPIRY_HOURS}h)')
    return f'{token_raw}.{signature}'


def validate_admin_session(token_composto: str, ip: str) -> dict | None:
    """
    Valida token de sessao admin.
    Retorna dict com dados da sessao ou None se invalido.

    Verificacoes:
    1. Formato do token (token.signature)
    2. HMAC-SHA256 do token
    3. Token hash existe no banco
    4. Sessao nao revogada
    5. Sessao nao expirada
    6. IP confere
    7. Dados criptografados intactos
    """
    if not token_composto or '.' not in token_composto:
        return None

    parts = token_composto.rsplit('.', 1)
    if len(parts) != 2:
        return None

    token_raw, signature = parts

    # 1. Verificar assinatura HMAC-SHA256
    if not verify_signature(token_raw, signature):
        log.warning('[ADMIN] Token com assinatura HMAC invalida')
        return None

    # 2. Buscar sessao no banco
    token_hash = _hash_token(token_raw)

    with _db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admin_sessions WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()

    if not row:
        log.warning('[ADMIN] Token nao encontrado no banco')
        return None

    # 3. Sessao revogada?
    if row['revoked']:
        log.warning(f'[ADMIN] Tentativa de usar sessao revogada: {row["user_email"]}')
        return None

    # 4. Expirada?
    if time.time() > row['expires_at']:
        log.warning(f'[ADMIN] Sessao expirada: {row["user_email"]}')
        # Revogar automaticamente
        with _admin_lock:
            with _db_conn() as conn:
                conn.execute(
                    "UPDATE admin_sessions SET revoked = 1 WHERE token_hash = ?",
                    (token_hash,),
                )
        return None

    # 5. IP confere?
    if row['ip_address'] != ip:
        log.warning(
            f'[ADMIN] IP divergente para {row["user_email"]}: '
            f'sessao={row["ip_address"]}, request={ip}'
        )
        return None

    # 6. Descriptografar dados
    decrypted = decrypt_payload(row['encrypted_data'])
    if not decrypted:
        log.error(f'[ADMIN] Falha ao descriptografar sessao: {row["user_email"]}')
        return None

    return {
        'email': row['user_email'],
        'ip': row['ip_address'],
        'created_at': row['created_at'],
        'session_data': decrypted,
    }


def revoke_admin_session(token_composto: str):
    """Revoga uma sessao admin especifica."""
    if not token_composto or '.' not in token_composto:
        return False

    token_raw = token_composto.rsplit('.', 1)[0]
    token_hash = _hash_token(token_raw)

    with _admin_lock:
        with _db_conn() as conn:
            updated = conn.execute(
                "UPDATE admin_sessions SET revoked = 1 WHERE token_hash = ?",
                (token_hash,),
            ).rowcount

    if updated:
        log.info('[ADMIN] Sessao revogada')
    return bool(updated)


def revoke_all_admin_sessions(email: str):
    """Revoga todas as sessoes de um admin."""
    email = email.strip().lower()
    with _admin_lock:
        with _db_conn() as conn:
            updated = conn.execute(
                "UPDATE admin_sessions SET revoked = 1 WHERE user_email = ? AND revoked = 0",
                (email,),
            ).rowcount
    log.info(f'[ADMIN] {updated} sessoes revogadas para {email}')
    return updated


def cleanup_expired_sessions():
    """Remove sessoes expiradas ou revogadas do banco."""
    with _admin_lock:
        with _db_conn() as conn:
            deleted = conn.execute(
                "DELETE FROM admin_sessions WHERE revoked = 1 OR expires_at < ?",
                (time.time(),),
            ).rowcount
    if deleted:
        log.info(f'[ADMIN] {deleted} sessoes expiradas removidas')
    return deleted


def list_active_sessions(email: str = None) -> list[dict]:
    """Lista sessoes admin ativas (opcionalmente filtra por email)."""
    with _db_conn() as conn:
        if email:
            rows = conn.execute(
                """SELECT user_email, ip_address, created_at, expires_at
                   FROM admin_sessions
                   WHERE user_email = ? AND revoked = 0 AND expires_at > ?""",
                (email.strip().lower(), time.time()),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT user_email, ip_address, created_at, expires_at
                   FROM admin_sessions
                   WHERE revoked = 0 AND expires_at > ?""",
                (time.time(),),
            ).fetchall()
    return [dict(r) for r in rows]
