"""Provider legado: wrapper do translate-shell (CLI) para compatibilidade."""

import shutil
import subprocess
from typing import Optional

from backend.engine.base import TranslationProvider


class TranslateShellProvider(TranslationProvider):
    """
    Wrapper do translate-shell existente.
    Mantido como ultimo fallback para compatibilidade.
    """

    def __init__(self, source_lang='en', target_lang='pt-br',
                 max_rpm=20, max_daily=3000):
        super().__init__(
            name='translate_shell',
            source_lang=source_lang,
            target_lang=target_lang,
            max_requests_per_minute=max_rpm,
            max_requests_per_day=max_daily,
        )

    def is_available(self) -> bool:
        return shutil.which('trans') is not None

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return text

        try:
            result = subprocess.run(
                ['trans', '-b', f'{self.source_lang}:{self.target_lang}', text],
                capture_output=True, text=True, timeout=8,
            )
            translated = result.stdout.strip()

            if result.returncode != 0 or not translated:
                self.record_failure(f"returncode={result.returncode}")
                return None

            if translated.lower() == text.strip().lower():
                self.record_failure(
                    "Traducao identica (rate-limit silencioso)",
                    is_rate_limit=True,
                )
                return None

            self.record_success()
            return translated

        except subprocess.TimeoutExpired:
            self.record_failure("Timeout")
            return None
        except Exception as e:
            self.record_failure(str(e))
            return None
