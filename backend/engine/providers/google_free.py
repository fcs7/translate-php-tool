"""Provider Google Translate gratuito via deep-translator (sem API key)."""

from typing import Optional

from backend.engine.base import TranslationProvider


class GoogleFreeProvider(TranslationProvider):
    """
    Google Translate via deep-translator (HTTP direto, sem CLI).
    Limite estimado: ~50 req/min, ~5000/dia antes de rate-limit.
    """

    def __init__(self, source_lang='en', target_lang='pt',
                 max_rpm=50, max_daily=5000):
        super().__init__(
            name='google_free',
            source_lang=source_lang,
            target_lang=target_lang,
            max_requests_per_minute=max_rpm,
            max_requests_per_day=max_daily,
        )
        self._translator = None

    def _get_translator(self):
        if self._translator is None:
            from deep_translator import GoogleTranslator
            self._translator = GoogleTranslator(
                source=self.source_lang,
                target=self.target_lang,
            )
        return self._translator

    def is_available(self) -> bool:
        try:
            self._get_translator()
            return True
        except Exception:
            return False

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return text

        try:
            translator = self._get_translator()
            result = translator.translate(text)

            if not result or result.strip().lower() == text.strip().lower():
                self.record_failure("Traducao identica ao original")
                return None

            self.record_success()
            return result.strip()

        except Exception as e:
            error_msg = str(e).lower()
            is_rate = 'rate' in error_msg or 'too many' in error_msg or '429' in error_msg
            self.record_failure(str(e), is_rate_limit=is_rate)
            return None
