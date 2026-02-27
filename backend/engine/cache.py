"""Cache de traducoes em 2 niveis: memoria (LRU) + SQLite (persistente)."""

import threading
from collections import OrderedDict
from typing import Callable, Optional, Tuple

from backend.config import log


class TwoLevelCache:
    """
    Nivel 1: OrderedDict em memoria (LRU, max 10k entradas)
    Nivel 2: SQLite (tabela translation_cache existente)
    """

    def __init__(self, db_get_fn: Callable, db_save_fn: Callable,
                 max_memory: int = 10_000):
        self._l1: OrderedDict = OrderedDict()
        self._max_memory = max_memory
        self._lock = threading.Lock()

        self._db_get = db_get_fn
        self._db_save = db_save_fn

        self.hits_l1 = 0
        self.hits_l2 = 0
        self.misses = 0
        self.total_lookups = 0

    def get(self, text: str) -> Tuple[Optional[str], str]:
        """Busca traducao. Retorna (traducao, nivel) onde nivel e 'l1', 'l2', ou 'miss'."""
        key = text.strip()

        with self._lock:
            self.total_lookups += 1
            if key in self._l1:
                self._l1.move_to_end(key)
                self.hits_l1 += 1
                return self._l1[key], 'l1'

        db_result = self._db_get(key)
        if db_result:
            with self._lock:
                self.hits_l2 += 1
            self._put_l1(key, db_result)
            return db_result, 'l2'

        with self._lock:
            self.misses += 1
        return None, 'miss'

    def put(self, text: str, translated: str, persist: bool = True):
        """Salva traducao nos 2 niveis."""
        key = text.strip()
        self._put_l1(key, translated)

        if persist:
            try:
                self._db_save(key, translated)
            except Exception as e:
                log.debug(f'[CACHE] Erro ao persistir: {e}')

    def _put_l1(self, key: str, value: str):
        """Insere no L1 com eviction LRU."""
        with self._lock:
            if key in self._l1:
                self._l1.move_to_end(key)
            else:
                if len(self._l1) >= self._max_memory:
                    self._l1.popitem(last=False)
                self._l1[key] = value

    def get_stats(self) -> dict:
        """Retorna metricas do cache."""
        total = self.total_lookups or 1
        return {
            'total_lookups': self.total_lookups,
            'hits_l1': self.hits_l1,
            'hits_l2': self.hits_l2,
            'misses': self.misses,
            'hit_rate_l1': f'{(self.hits_l1 / total) * 100:.1f}%',
            'hit_rate_total': f'{((self.hits_l1 + self.hits_l2) / total) * 100:.1f}%',
            'l1_size': len(self._l1),
            'l1_max': self._max_memory,
        }

    def warm_up(self, limit: int = 5000):
        """Pre-carrega as traducoes mais usadas do SQLite para L1."""
        try:
            from backend.auth import _db_conn, _db_lock
            with _db_lock:
                with _db_conn() as conn:
                    rows = conn.execute(
                        "SELECT source_text, translated_text FROM translation_cache "
                        "ORDER BY hit_count DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                    for row in rows:
                        self._put_l1(row['source_text'], row['translated_text'])
                    log.info(f'[CACHE] Warm-up: {len(rows)} traducoes carregadas em memoria')
        except Exception as e:
            log.warning(f'[CACHE] Erro no warm-up: {e}')
