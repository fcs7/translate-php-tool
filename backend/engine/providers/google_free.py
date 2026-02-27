"""Provider Google Translate gratuito via HTTP direto (sem dependencias externas)."""

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from backend.engine.base import TranslationProvider


class GoogleFreeProvider(TranslationProvider):
    """
    Google Translate via HTTP direto ao endpoint gtx (mesmo que deep-translator usa).
    Timeout de 8s por request. Batch usa ThreadPoolExecutor com 10 workers.
    Limite estimado: ~50 req/min, ~5000/dia antes de rate-limit.
    """

    TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, source_lang='en', target_lang='pt',
                 max_rpm=50, max_daily=5000):
        super().__init__(
            name='google_free',
            source_lang=source_lang,
            target_lang=target_lang,
            max_requests_per_minute=max_rpm,
            max_requests_per_day=max_daily,
        )

    def is_available(self) -> bool:
        return True

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return text

        try:
            params = urllib.parse.urlencode({
                'client': 'gtx',
                'sl': self.source_lang,
                'tl': self.target_lang,
                'dt': 't',
                'q': text,
            })
            url = f"{self.TRANSLATE_URL}?{params}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
            })

            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            # Resposta do Google: [[["traducao","original",...],...],...]
            translated = ''.join(
                part[0] for part in data[0] if part and part[0]
            )

            if not translated or translated.strip().lower() == text.strip().lower():
                self.record_failure("Traducao identica ao original")
                return None

            self.record_success()
            return translated.strip()

        except Exception as e:
            error_msg = str(e).lower()
            is_rate = 'rate' in error_msg or 'too many' in error_msg or '429' in error_msg
            self.record_failure(str(e), is_rate_limit=is_rate)
            return None

    def translate_batch(self, texts: List[str]) -> List[Optional[str]]:
        """Batch via ThreadPoolExecutor — N requests em paralelo, max 10 concurrent."""
        if not texts:
            return []

        results = [None] * len(texts)

        # Separar textos vazios (não precisam de request)
        tasks = {}
        for i, text in enumerate(texts):
            if not text.strip():
                results[i] = text
            else:
                tasks[i] = text

        if not tasks:
            return results

        try:
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {
                    pool.submit(self.translate, text): idx
                    for idx, text in tasks.items()
                }

                for future in as_completed(futures, timeout=15):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                    except Exception:
                        results[idx] = None

        except TimeoutError:
            # as_completed timeout — alguns requests não terminaram a tempo
            self.record_failure("Batch timeout (15s)", is_rate_limit=False)

        return results
