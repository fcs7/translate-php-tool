"""Classe base abstrata para provedores de traducao."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderStatus(Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ProviderStats:
    """Estatisticas de uso de um provider."""

    name: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    rate_limited: int = 0
    last_request_at: float = 0.0
    last_error_at: float = 0.0
    last_error_msg: str = ""
    cooldown_until: float = 0.0
    requests_this_window: int = 0
    window_start: float = field(default_factory=time.time)


class TranslationProvider(ABC):
    """Interface abstrata para provedores de traducao."""

    def __init__(self, name: str, source_lang: str = 'en',
                 target_lang: str = 'pt-br',
                 max_requests_per_minute: int = 60,
                 max_requests_per_day: int = 5000):
        self.name = name
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.max_rpm = max_requests_per_minute
        self.max_daily = max_requests_per_day
        self.stats = ProviderStats(name=name)

    @abstractmethod
    def translate(self, text: str) -> Optional[str]:
        """Traduz texto. Retorna string traduzida ou None em caso de falha."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o provider esta disponivel."""
        ...

    def check_rate_limit(self) -> bool:
        """Verifica preventivamente se pode fazer mais uma request."""
        now = time.time()

        if now < self.stats.cooldown_until:
            return False

        # Resetar janela de 60s
        if now - self.stats.window_start > 60:
            self.stats.requests_this_window = 0
            self.stats.window_start = now

        if self.stats.requests_this_window >= self.max_rpm:
            return False

        return True

    def record_success(self):
        """Registra traducao bem-sucedida."""
        self.stats.total_requests += 1
        self.stats.successful += 1
        self.stats.requests_this_window += 1
        self.stats.last_request_at = time.time()

    def record_failure(self, error_msg: str = "", is_rate_limit: bool = False):
        """Registra falha com cooldown progressivo."""
        now = time.time()
        self.stats.total_requests += 1
        self.stats.failed += 1
        self.stats.last_error_at = now
        self.stats.last_error_msg = error_msg

        if is_rate_limit:
            self.stats.rate_limited += 1
            consecutive = min(self.stats.rate_limited, 4)
            cooldown = 30 * (2 ** consecutive)
            self.stats.cooldown_until = now + cooldown

    def get_status(self) -> ProviderStatus:
        """Retorna status atual do provider."""
        if not self.is_available():
            return ProviderStatus.DISABLED
        if time.time() < self.stats.cooldown_until:
            return ProviderStatus.RATE_LIMITED
        return ProviderStatus.AVAILABLE
