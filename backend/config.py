"""Configuracoes centralizadas do backend."""

import os
import logging

# Diretorios base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Armazenamento
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
JOBS_FOLDER = os.path.join(BASE_DIR, 'jobs')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
LOG_FILE = os.path.join(BASE_DIR, 'trans-script.log')

# Limites
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
MAX_CONCURRENT_JOBS = 3
RATE_LIMIT_SECONDS = 5  # Intervalo minimo entre uploads por IP

# Traducao
DEFAULT_DELAY = 0.2
SOURCE_LANG = 'en'
TARGET_LANG = 'pt-br'

# Garantir que diretorios existem
for _folder in [UPLOAD_FOLDER, JOBS_FOLDER]:
    os.makedirs(_folder, exist_ok=True)


# ============================================================================
# Logging
# ============================================================================

def setup_logging():
    """Configura logging para console + arquivo."""
    fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # Arquivo
    fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    root = logging.getLogger('trans-script')
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    return root


log = setup_logging()
