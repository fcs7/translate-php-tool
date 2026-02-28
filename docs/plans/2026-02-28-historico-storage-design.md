# Design: Sistema de Historico e Storage por Usuario

**Data:** 2026-02-28
**Status:** Aprovado
**Abordagem:** Fix & Enhance (corrigir problemas existentes + adicionar funcionalidades)

## Contexto

O sistema atual tem infraestrutura de historico (`job_history`) e quota (`storage_used_bytes`/`storage_limit_bytes`) no SQLite, mas varios problemas impedem o funcionamento correto:

1. Cleanup so roda no `__main__` (Gunicorn ignora)
2. Sem cleanup periodico — jobs expirados acumulam em disco
3. `storage_used_bytes` pode desincronizar em crash
4. Sem endpoint de delete do historico pelo usuario
5. Sem delete em massa
6. Mensagem de quota generica, sem sugestao de acao
7. `job_history` nao salva tamanho do job

## Requisitos

- **500MB por usuario** de limite de storage
- **7 dias** de expiracao para arquivos de download (ZIP/TAR)
- **Bloquear upload + sugerir limpeza** quando limite atingido
- **Delete individual + em massa** pelo usuario
- **Metadados sempre mantidos** no DB para admin (audit trail)
- **Monetizacao TBD** — preparar infraestrutura agora

## Design

### 1. Cleanup Periodico

Background thread daemon iniciado com o app.

- **Intervalo:** 24 horas (1x/dia)
- **Fluxo:**
  1. `cleanup_expired_jobs()` retorna job_ids expirados
  2. Para cada job expirado:
     - Remove arquivos do disco (`shutil.rmtree` da pasta `jobs/{job_id}/`)
     - Atualiza `storage_used_bytes` do usuario (negativo)
     - Marca `file_available=0` no `job_history`
     - **NAO** deleta registro do `job_history` (mantido para admin)
  3. Limpa sessions admin expiradas
  4. Log: `[CLEANUP] N jobs expirados limpos, X MB liberados`

**Nova funcao:** `expire_job_files(job_id)` — diferente de `delete_job()` que deleta tudo. Esta funcao so remove arquivos e atualiza quota, preservando historico.

**Inicializacao:** Thread daemon criada em `create_app()` ou via `@app.before_first_request`.

### 2. Endpoints de Delete

| Metodo | Rota | Acao |
|--------|------|------|
| `DELETE` | `/api/history/<job_id>` | Deleta arquivos de 1 job, marca `file_available=0`, atualiza quota |
| `DELETE` | `/api/history?expired_only=true` | Bulk: deleta arquivos de todos os jobs do usuario (ou so expirados) |
| `GET` | `/api/quota` | Retorna quota atual do usuario |
| `DELETE` | `/api/admin/users/<id>/history/<job_id>` | Admin deleta job de qualquer usuario |
| `POST` | `/api/admin/reconcile-storage` | Recalcula storage de todos os usuarios a partir do disco |

**Regras:**
- Verificacao de ownership: `user_email == session['user_email']`
- Resposta inclui `freed_bytes` e `quota` atualizado
- Admin pode deletar de qualquer usuario

### 3. Quota Enforcement + UX

**Backend — resposta enriquecida quando quota excedida:**
```json
{
  "error": "Cota excedida",
  "quota": {"used_mb": 487, "limit_mb": 500, "percent": 97.4},
  "deletable_jobs": [
    {"job_id": "abc123", "size_mb": 45.2, "created_at": "...", "expired": true}
  ]
}
```

**Frontend — `UserHistory.jsx`:**
- Barra de quota: verde (< 70%), amarelo (70-90%), vermelho (> 90%)
- Botao de delete por job (icone lixeira)
- Botao "Liberar espaco" no topo quando quota > 80%
- Confirmacao antes de delete em massa

**Frontend — tela de upload:**
- Bloqueio visual quando quota >= 100%
- Mensagem: "Armazenamento cheio (487 MB / 500 MB)"
- Botao "Gerenciar historico" redireciona para UserHistory

**Frontend — apos upload falhar por quota:**
- Toast/modal com lista dos maiores jobs e opcao de deletar

### 4. Schema Migration

Adicionar coluna `file_size_bytes` na tabela `job_history`:
```sql
ALTER TABLE job_history ADD COLUMN file_size_bytes INTEGER DEFAULT 0;
```

- `save_job_history()` passa a salvar o tamanho do job
- Permite mostrar tamanho de cada job na UI do historico

### 5. Reconciliacao Admin

- Endpoint `POST /api/admin/reconcile-storage`
- Escaneia disco para cada usuario, compara com `storage_used_bytes` no DB
- Corrige discrepancias automaticamente
- Retorna relatorio: `{"users_fixed": 3, "total_delta_mb": -127.5}`
- Botao no painel admin
- Log: `[RECONCILE] user@email: DB=450MB, disk=322MB, corrigido`

## Arquivos Afetados

### Backend
- `backend/auth.py` — nova funcao `expire_job_files()`, migration `file_size_bytes`, endpoint helpers
- `backend/app.py` — novos endpoints, cleanup thread, quota response enriquecida
- `backend/translator.py` — salvar `file_size_bytes` no `save_job_history()`

### Frontend
- `frontend/src/components/UserHistory.jsx` — barra de quota, botoes delete, confirmacao
- `frontend/src/pages/AdminPanel.jsx` — botao reconcile
- `frontend/src/services/api.js` — novos endpoints
- `frontend/src/App.jsx` — bloqueio de upload quando quota cheia

## O que NAO muda

- Tabela `job_history` continua existindo (metadados nunca deletados)
- Fluxo de traducao inalterado
- Engine de traducao inalterada
- Sistema de autenticacao inalterado
- `JOB_EXPIRY_DAYS = 7` mantido como padrao
