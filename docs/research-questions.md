# Perguntas de Pesquisa — Trans-Script

## Perguntas Prioritarias (Responder Primeiro)

### P1: Qual API tem melhor qualidade para PT-BR?
- Comparar BLEU scores ou benchmarks Intento para EN→PT-BR
- DeepL vs Google Cloud vs Amazon Translate vs NLLB
- Considerar que sao strings curtas de UI (nao textos longos)
- Exemplo de string: "You have {count} new messages"

### P2: Qual combinacao de APIs cobre 100% das 10.509 strings no free tier?
- Google Free: ~4800 antes de rate-limit
- Quanto sobra para a segunda API? (~5700 strings, ~342K chars)
- Qual free tier cobre isso?
- E se tiver 20K strings? 50K?

### P3: Vale a pena self-host (LibreTranslate, NLLB, Ollama)?
- Qual hardware minimo?
- Qualidade comparada com APIs comerciais?
- Latencia: GPU vs CPU?
- Memoria RAM necessaria?
- VPS de $10-20/mes aguenta?

### P4: Como projetos similares (Weblate, Crowdin) resolvem o rate-limit?
- Usam queue? Circuit breaker?
- Fazem retry por string ou por batch?
- Como decidem qual provider usar?

---

## Perguntas de Arquitetura

### P5: Async (aiohttp) vs Threads para I/O de traducao?
- O projeto usa `urllib.request` (sincrono)
- Vale migrar para `aiohttp`? Quebra a restricao de stdlib?
- `asyncio` com `run_in_executor` e alternativa viavel?
- Benchmark: threads vs async para 10K requests HTTP

### P6: Qual batch size ideal por provider?
- Google Free: aceita 1 texto/request (batch = N requests paralelas)
- DeepL Free: aceita 50 textos/request — pode mais?
- MyMemory: aceita 1 texto/request
- Qual overhead de batch vs single?
- Batch adaptativo (comecar grande, reduzir se falhar)?

### P7: Como fazer provider health scoring?
- Weblate faz isso? Crowdin?
- Metricas: latencia media, taxa de sucesso, custo
- Reordenar chain dinamicamente baseado em performance?
- Circuit breaker: quando desligar um provider?

### P8: Cache — o que melhorar?
- Cache atual: dict + SQLite (warm-up no inicio)
- Redis vale a pena? (adiciona dependencia)
- TTL por traducao (traducoes ficam obsoletas?)
- Cache por provider (mesma string, traducoes diferentes)?
- Pre-warming: carregar traducoes de jobs anteriores?

---

## Perguntas de Escala

### P9: Como escalar para 50K+ strings?
- Queue system (Celery + Redis)?
- Multiplos workers Gunicorn?
- Separar traducao em microservico?
- Kubernetes? Docker Swarm?

### P10: Como lidar com upload de multiplos projetos simultaneos?
- MAX_CONCURRENT_JOBS = 3 (atual)
- Compartilhar rate-limit entre jobs?
- Prioridade de jobs (FIFO? por tamanho?)

---

## Perguntas de Custo

### P11: Qual custo mensal para 100K strings/mes?
- Cenario 1: Tudo gratis (Google Free + fallbacks)
- Cenario 2: DeepL Free (500K chars) + Google Free
- Cenario 3: Google Cloud ($20/1M chars)
- Cenario 4: Self-hosted (VPS $10-20/mes)
- Cenario 5: Mix otimizado (qual?)

### P12: ROI de cada provider pago
- Se pagar $10/mes, quantas strings a mais traduz?
- Qual provider tem melhor custo-beneficio para PT-BR?
- Free tier generoso vs pago barato?
