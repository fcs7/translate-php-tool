# Trans-Script — Arquitetura Atual (Fev 2026)

## Visao Geral

Aplicacao web para traducao automatica de arquivos de localizacao PHP (EN → PT-BR).
Upload de ZIP/TAR/RAR → Traducao em batch → Download ZIP + VoipNow TAR.

```
┌─────────────┐     WebSocket      ┌──────────────────────────────────────┐
│  React SPA  │ ◄────────────────► │  Flask + SocketIO (Gunicorn)         │
│  (Vite)     │                    │                                      │
│             │  REST API          │  ┌─────────────┐  ┌───────────────┐  │
│  - Upload   │ ◄────────────────► │  │ translator  │  │ auth (OTP)    │  │
│  - Progress │                    │  │ .py         │  │ users.db      │  │
│  - Download │                    │  └──────┬──────┘  └───────────────┘  │
└─────────────┘                    │         │                             │
                                   │  ┌──────▼──────────────────────────┐  │
                                   │  │ TranslationEngine              │  │
                                   │  │                                │  │
                                   │  │  Cache (2 niveis)              │  │
                                   │  │  ├── L1: dict in-memory (10K)  │  │
                                   │  │  └── L2: SQLite (users.db)     │  │
                                   │  │                                │  │
                                   │  │  Chain of Responsibility:      │  │
                                   │  │  1. GoogleFreeProvider         │  │
                                   │  │  2. MyMemoryProvider           │  │
                                   │  │  3. DeepLFreeProvider          │  │
                                   │  │  4. TranslateShellProvider     │  │
                                   │  └────────────────────────────────┘  │
                                   └──────────────────────────────────────┘
```

## Fluxo de Traducao

```
1. Usuario faz upload (ZIP com PHPs)
2. Backend extrai arquivo → /backend/jobs/{job_id}/input/
3. Thread de traducao inicia (_run)
4. Para cada arquivo PHP (SEQUENCIAL):
   a. Pass 1: Coleta strings traduziveis ($msg_arr[...] = '...')
   b. Pass 2: Traduz em batches de BATCH_SIZE=50
      - Engine tenta cache primeiro
      - Se nao cached: tenta provider 1, 2, 3...
      - Cada batch: emit WebSocket com progresso
   c. Pass 3: Grava arquivo traduzido
5. Cria ZIP + VoipNow TAR de saida
6. Emite evento 'translation_complete'
```

## Arquivos Principais

| Arquivo | Funcao | Linhas |
|---------|--------|--------|
| `backend/translator.py` | Orquestracao: jobs, threads, batch loop | ~560 |
| `backend/engine/engine.py` | TranslationEngine: cache + fallback chain | ~200 |
| `backend/engine/base.py` | TranslationProvider: interface abstrata | ~107 |
| `backend/engine/__init__.py` | Singleton factory: monta chain | ~75 |
| `backend/engine/providers/google_free.py` | Google Free: HTTP direto, 10 workers | ~108 |
| `backend/engine/providers/deepl_free.py` | DeepL Free API: batch nativo | ~125 |
| `backend/engine/providers/mymemory.py` | MyMemory: zero dependencia | ~71 |
| `backend/engine/providers/translate_shell.py` | translate-shell: CLI wrapper | ~59 |
| `backend/engine/cache.py` | TwoLevelCache: memory + SQLite | ~??? |
| `backend/config.py` | Configuracoes centralizadas | ~79 |
| `backend/app.py` | Flask routes + SocketIO | ~??? |
| `backend/auth.py` | Autenticacao OTP + DB helpers | ~??? |

## Interface do Provider (Contrato)

```python
class TranslationProvider(ABC):
    name: str
    source_lang: str
    target_lang: str
    stats: ProviderStats

    # Obrigatorios
    def translate(text: str) -> Optional[str]       # 1 texto
    def is_available() -> bool                       # disponivel?

    # Default (override para batch nativo)
    def translate_batch(texts: List[str]) -> List[Optional[str]]

    # Rate-limit helpers (herdados)
    def check_rate_limit() -> bool
    def record_success()
    def record_failure(error_msg, is_rate_limit)
    def get_status() -> ProviderStatus
```

## Problemas Conhecidos

### Performance
- **Arquivos sequenciais**: 14 arquivos traduzidos 1 por vez
- **Batch size**: fixo em 50 (poderia ser adaptativo)
- **Sem paralelismo de arquivo**: thread unica para todos os arquivos
- **job.translated_strings += 1**: nao e thread-safe (problematico se paralelizar)

### Rate-Limiting
- Google Free: rate-limit ciclico apos ~4800 strings
- Cooldown exponencial: 30s × 2^N (max 480s)
- Quando Google falha, MyMemory e tentado antes do DeepL (subotimo)
- Chain order: DeepL deveria vir antes de MyMemory

### Escala
- 1 worker Gunicorn (WebSocket requer gevent single-worker)
- Sem queue system (tudo em threads)
- Sem retry inteligente por string individual
- Cache nao persiste entre restarts do servidor (L1 memory)

## Metricas do Teste Real (10.509 strings)

- Google Free: ~4800 OK, depois rate-limit
- MyMemory: baixa qualidade, muitas traducoes identicas ao original
- DeepL: nao testado (sem API key configurada)
- translate-shell: funciona mas muito lento (1 por vez)
- **Resultado**: 7698 traduzidas (73%), 2811 falharam (27%)

## Stack Tecnico

- **Backend**: Python 3.11, Flask, Flask-SocketIO, Gunicorn (gevent)
- **Frontend**: React 19, Vite, TailwindCSS
- **DB**: SQLite (users + cache + jobs)
- **Deploy**: deploy.sh (Nginx + Certbot + systemd)
- **Restricao**: apenas stdlib Python para providers (sem requests/httpx)
