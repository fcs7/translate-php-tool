"""Modulo engine — inicializacao singleton da engine de traducao."""

import os
import threading
from typing import Optional

from backend.config import log
from backend.engine.engine import TranslationEngine
from backend.engine.cache import TwoLevelCache
from backend.auth import get_cached_translation_db, save_cached_translation_db

_engine: Optional[TranslationEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> TranslationEngine:
    """Retorna singleton da engine de traducao (thread-safe, double-checked locking)."""
    global _engine
    if _engine is not None:
        return _engine

    with _engine_lock:
        if _engine is not None:
            return _engine

        # Cache de 2 niveis
        cache = TwoLevelCache(
            db_get_fn=get_cached_translation_db,
            db_save_fn=save_cached_translation_db,
            max_memory=int(os.environ.get('CACHE_MEMORY_SIZE', '10000')),
        )
        cache.warm_up()

        # Montar chain de providers
        providers = []

        # 1. Google Free (principal, sem API key)
        try:
            from backend.engine.providers.google_free import GoogleFreeProvider
            gf = GoogleFreeProvider(source_lang='en', target_lang='pt')
            if gf.is_available():
                providers.append(gf)
                log.info('[ENGINE] Provider google_free adicionado')
        except Exception as e:
            log.warning(f'[ENGINE] Google Free indisponivel: {e}')

        # 2. DeepL Free (fallback premium, requer API key gratuita)
        deepl_key = os.environ.get('DEEPL_API_KEY', '')
        if deepl_key:
            from backend.engine.providers.deepl_free import DeepLFreeProvider
            providers.append(DeepLFreeProvider(api_key=deepl_key))
            log.info('[ENGINE] Provider deepl_free adicionado')

        # 3. MyMemory (fallback gratis, zero dependencia)
        from backend.engine.providers.mymemory import MyMemoryProvider
        providers.append(MyMemoryProvider(
            source_lang='en',
            target_lang='pt-br',
            email=os.environ.get('MYMEMORY_EMAIL'),
        ))
        log.info('[ENGINE] Provider mymemory adicionado')

        # 4. translate-shell legado (ultimo recurso)
        from backend.engine.providers.translate_shell import TranslateShellProvider
        shell = TranslateShellProvider()
        if shell.is_available():
            providers.append(shell)
            log.info('[ENGINE] Provider translate_shell adicionado')

        if not providers:
            raise RuntimeError('Nenhum provider de traducao disponivel!')

        _engine = TranslationEngine(providers, cache)
        return _engine
