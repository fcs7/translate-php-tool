"""Provider DeepL Free API (500k chars/mes, requer API key gratuita)."""

import json
import urllib.parse
import urllib.request
from typing import Optional

from backend.engine.base import TranslationProvider


class DeepLFreeProvider(TranslationProvider):
    """
    DeepL Free API — 500.000 chars/mes com API key gratuita.
    Melhor qualidade para linguas europeias.
    Usa apenas stdlib (urllib).
    """

    API_URL = "https://api-free.deepl.com/v2/translate"

    def __init__(self, api_key: str = '', source_lang='EN',
                 target_lang='PT-BR', max_rpm=30, max_daily=10000):
        super().__init__(
            name='deepl_free',
            source_lang=source_lang,
            target_lang=target_lang,
            max_requests_per_minute=max_rpm,
            max_requests_per_day=max_daily,
        )
        self.api_key = api_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return text
        if not self.api_key:
            return None

        try:
            data = urllib.parse.urlencode({
                'auth_key': self.api_key,
                'text': text,
                'source_lang': self.source_lang,
                'target_lang': self.target_lang,
            }).encode('utf-8')

            req = urllib.request.Request(self.API_URL, data=data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            translations = result.get('translations', [])
            if not translations:
                self.record_failure("Resposta vazia da API")
                return None

            translated = translations[0].get('text', '').strip()
            if not translated or translated.lower() == text.strip().lower():
                self.record_failure("Traducao identica ao original")
                return None

            self.record_success()
            return translated

        except Exception as e:
            error_msg = str(e)
            is_rate = '429' in error_msg or '456' in error_msg
            self.record_failure(error_msg, is_rate_limit=is_rate)
            return None
