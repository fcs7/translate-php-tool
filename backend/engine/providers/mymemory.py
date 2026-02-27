"""Provider MyMemory Translation API (gratuita, zero dependencias extras)."""

import json
import urllib.parse
import urllib.request
from typing import Optional

from backend.engine.base import TranslationProvider


class MyMemoryProvider(TranslationProvider):
    """
    MyMemory API — gratuita, 5000 chars/dia sem registro.
    Com email de registro: 50.000 chars/dia.
    Usa apenas stdlib (urllib).
    """

    API_URL = "https://api.mymemory.translated.net/get"

    def __init__(self, source_lang='en', target_lang='pt-br',
                 email=None, max_rpm=30, max_daily=5000):
        super().__init__(
            name='mymemory',
            source_lang=source_lang,
            target_lang=target_lang,
            max_requests_per_minute=max_rpm,
            max_requests_per_day=max_daily,
        )
        self.email = email

    def is_available(self) -> bool:
        return True

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return text

        try:
            params = {
                'q': text,
                'langpair': f'{self.source_lang}|{self.target_lang}',
            }
            if self.email:
                params['de'] = self.email

            url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'TransScript/1.0',
            })

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            status = data.get('responseStatus', 0)
            if status == 429:
                self.record_failure("Rate limited", is_rate_limit=True)
                return None

            match = data.get('responseData', {}).get('translatedText', '')
            if not match or match.strip().lower() == text.strip().lower():
                self.record_failure("Traducao identica ao original")
                return None

            self.record_success()
            return match.strip()

        except Exception as e:
            error_msg = str(e)
            is_rate = '429' in error_msg
            self.record_failure(error_msg, is_rate_limit=is_rate)
            return None
