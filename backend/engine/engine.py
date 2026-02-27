"""TranslationEngine — orquestrador principal com fallback chain."""

import time
from typing import List, Optional

from backend.config import log
from backend.engine.base import TranslationProvider, ProviderStatus
from backend.engine.cache import TwoLevelCache


class TranslationEngine:
    """
    Engine de traducao com:
    - Cache de 2 niveis (memoria + SQLite)
    - Chain of Responsibility: tenta providers em ordem
    - Rate-limit awareness preventivo
    - Metricas por provider
    """

    def __init__(self, providers: List[TranslationProvider], cache: TwoLevelCache):
        self.providers = providers
        self.cache = cache

        available = [p.name for p in providers if p.is_available()]
        log.info(f'[ENGINE] Inicializado com providers: {[p.name for p in providers]}')
        log.info(f'[ENGINE] Disponiveis: {available}')

    def translate(self, text: str, delay: float = 0.2) -> str:
        """
        Traduz texto usando cache + fallback chain.
        Retorna texto traduzido, ou o original como ultimo recurso.
        """
        if not text.strip():
            return text

        # 1. Verificar cache
        cached, level = self.cache.get(text)
        if cached:
            return cached

        # 2. Tentar cada provider na chain
        for provider in self.providers:
            status = provider.get_status()

            if status == ProviderStatus.DISABLED:
                continue

            if status == ProviderStatus.RATE_LIMITED:
                remaining = provider.stats.cooldown_until - time.time()
                log.debug(
                    f'[ENGINE] {provider.name} em cooldown '
                    f'({remaining:.0f}s restantes)'
                )
                continue

            if not provider.check_rate_limit():
                log.debug(
                    f'[ENGINE] {provider.name} atingiu RPM limit, '
                    f'tentando proximo'
                )
                continue

            log.debug(f'[ENGINE] Tentando {provider.name} para: {text[:50]}...')
            result = provider.translate(text)

            if result and result.strip().lower() != text.strip().lower():
                self.cache.put(text, result, persist=True)
                return result

            log.debug(
                f'[ENGINE] {provider.name} falhou, tentando proximo provider'
            )
            time.sleep(0.5)

        # 3. Nenhum provider conseguiu
        log.warning(f'[ENGINE] TODOS providers falharam para: {text[:60]}...')
        return text

    def get_active_provider(self) -> Optional[str]:
        """Retorna o nome do primeiro provider disponivel."""
        for p in self.providers:
            if p.get_status() == ProviderStatus.AVAILABLE:
                return p.name
        return None

    def get_stats(self) -> dict:
        """Retorna metricas completas da engine."""
        return {
            'cache': self.cache.get_stats(),
            'providers': {
                p.name: {
                    'status': p.get_status().value,
                    'total_requests': p.stats.total_requests,
                    'successful': p.stats.successful,
                    'failed': p.stats.failed,
                    'rate_limited': p.stats.rate_limited,
                    'success_rate': f'{(p.stats.successful / max(p.stats.total_requests, 1)) * 100:.1f}%',
                }
                for p in self.providers
            },
            'active_provider': self.get_active_provider(),
        }
