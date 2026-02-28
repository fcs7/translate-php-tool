# Prompt: Agente de Pesquisa — Melhor API de Traducao + Arquitetura

## Missao

Voce e um agente de pesquisa especializado em APIs de traducao e arquitetura de aplicacoes web de traducao em batch. Sua missao e pesquisar, comparar e recomendar a melhor solucao para o projeto Trans-Script.

## Contexto do Projeto

Trans-Script e uma aplicacao web (Python/Flask + React) que traduz arquivos de localizacao PHP (EN → PT-BR) em batch. O projeto usa uma engine multi-provider com fallback chain.

### Problema Atual
- **10.509 strings** para traduzir
- Google Free funciona bem ate ~4.800 strings, depois entra em rate-limit ciclico
- **27% de falha** (2.811 strings) por rate-limiting
- Precisa de uma API complementar de qualidade para cobrir o restante

### Arquitetura Atual
```
Frontend (React) → Backend (Flask + SocketIO) → Engine de Traducao
                                                  ├── Cache 2 niveis (memoria + SQLite)
                                                  └── Chain of Responsibility:
                                                      1. Google Free (ilimitado, rate-limited)
                                                      2. MyMemory (fallback gratis)
                                                      3. DeepL Free (500K chars/mes, requer API key)
                                                      4. translate-shell (ultimo recurso)
```

### Restricoes Tecnicas
- **Python 3.6+** com stdlib apenas (sem libs externas para providers)
- Provider usa `urllib.request` (sem requests/httpx)
- Interface abstrata: `TranslationProvider` com `translate()`, `translate_batch()`, `is_available()`
- Deploy em VPS com Gunicorn + Nginx + systemd

---

## Pesquisa Necessaria

### 1. APIs de Traducao — Comparacao Detalhada

Pesquise e compare TODAS as APIs de traducao disponiveis em 2025-2026, incluindo:

| Criterio | O que pesquisar |
|----------|-----------------|
| **Free tier** | Chars/mes, strings/mes, requests/mes |
| **Qualidade PT-BR** | Benchmarks (Intento, BLEU scores), testes manuais |
| **Batch nativo** | API aceita N textos em 1 request? Limite? |
| **Rate limits** | RPM, chars/min, burst |
| **Latencia** | ms por request, ms por batch |
| **SDK/Auth** | API key? OAuth? Complexidade de setup |
| **Preco apos free** | $/1M chars no tier pago |

**APIs para pesquisar (minimo):**
- DeepL Free / Pro
- Google Cloud Translation (v2 e v3)
- Microsoft Azure Translator
- Amazon Translate
- Yandex Translate
- Papago (Naver)
- LibreTranslate (self-hosted)
- Lingva Translate (self-hosted)
- MyMemory
- Reverso API
- ModernMT
- NLLB (Meta, open-source)
- Ollama + modelos locais (ex: MADLAD-400, Helsinki-NLP)
- OpenAI / Claude para traducao
- Groq + modelos de traducao

### 2. Aplicacoes Similares — Analise de Referencia

Pesquise projetos open-source e SaaS que fazem traducao em batch:

**Projetos para analisar:**
- **Weblate** — como gerencia providers e fallback?
- **Pontoon** (Mozilla) — arquitetura de traducao
- **Crowdin** — como faz batch + paralelismo?
- **Lokalise** — API design patterns
- **i18next** ecossistema — como integra com APIs
- **deep-translator** (Python) — como abstrai providers
- **translators** (Python) — como faz fallback
- **argos-translate** — traducao offline
- **LibreTranslate** — self-hosted, como escala?

**Para cada projeto, documentar:**
1. Arquitetura de providers (como fazem fallback?)
2. Estrategia de cache (em disco? Redis? SQLite?)
3. Paralelismo (threads? async? workers?)
4. Rate-limit handling (retry? backoff? circuit breaker?)
5. Batch processing (tamanho ideal? streaming?)
6. Queue system (Celery? Redis Queue? threads?)

### 3. Padroes de Arquitetura

Pesquise best practices para:
- **Circuit Breaker** para APIs externas
- **Adaptive batch sizing** (ajustar batch size baseado em taxa de sucesso)
- **Provider health scoring** (rankear providers dinamicamente)
- **Streaming translation** (traduzir enquanto faz upload)
- **Queue-based translation** (Redis/Celery vs ThreadPool)
- **Cost optimization** (rotacionar providers por custo)

### 4. Performance e Escala

- Qual batch size ideal para cada API?
- Quantas requests paralelas cada API suporta?
- Vale a pena async (aiohttp) vs threads para I/O bound?
- Como VPS com 4+ cores melhora o throughput?
- Qual o gargalo real: CPU, I/O, rate-limit?

---

## Formato de Saida Esperado

### Para cada API pesquisada:
```markdown
## [Nome da API]

**Free tier:** X chars/mes | Y requests/mes
**Qualidade PT-BR:** [Excelente/Boa/Razoavel] — benchmark: X
**Batch:** [Sim/Nao] — max N textos/request
**Rate limit:** X req/min, Y chars/min
**Latencia media:** Xms (single), Yms (batch de 50)
**Auth:** [API Key / OAuth / Nenhum]
**Preco pago:** $X/1M chars
**Pros:** ...
**Contras:** ...
**Facilidade de implementar:** [Facil/Medio/Dificil] — precisa de: ...
**Recomendacao:** [Sim/Nao/Talvez] — porque: ...
```

### Para cada projeto de referencia:
```markdown
## [Nome do Projeto]

**URL:** ...
**Stack:** ...
**Como faz fallback:** ...
**Como faz batch:** ...
**Como faz cache:** ...
**Insight principal:** ...
**O que podemos copiar:** ...
```

### Recomendacao Final:
```markdown
## Estrategia Recomendada

**Providers (em ordem):**
1. [Provider 1] — motivo
2. [Provider 2] — motivo
3. ...

**Batch size ideal:** X (baseado em: ...)
**Paralelismo:** [estrategia] (baseado em: ...)
**Cache:** [estrategia] (baseado em: ...)
**Estimativa de cobertura:** X% das 10.509 strings
**Custo mensal estimado:** $X
```

---

## Restricoes da Pesquisa

- **NAO recomendar Azure** (usuario descartou)
- Priorizar solucoes com free tier generoso
- Priorizar qualidade para PT-BR especificamente
- Solucao deve funcionar com `urllib` (sem dependencias externas)
- Considerar que o deploy e em VPS Linux (pode self-host)
- Foco em solucoes que complementem o Google Free existente
