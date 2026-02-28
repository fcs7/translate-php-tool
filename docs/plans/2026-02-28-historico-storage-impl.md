# Historico & Storage — Plano de Implementacao

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Corrigir sistema de historico e storage do Trans-Script Web — cleanup periodico, delete de jobs, quota enforcement, e reconciliacao admin.

**Architecture:** Abordagem "Fix & Enhance" sobre a infraestrutura existente (SQLite + Flask). Adiciona background cleanup thread, novos endpoints REST, e UX de quota no frontend React. Nenhuma dependencia nova.

**Tech Stack:** Python 3.6+ (Flask, SQLite, threading), React (Vite + TailwindCSS)

---

### Task 1: Schema Migration — `file_size_bytes` em `job_history`

**Files:**
- Modify: `backend/auth.py:48-133` (funcao `init_db()`)
- Modify: `backend/auth.py:539-562` (funcao `save_job_history()`)
- Modify: `backend/auth.py:565-574` (funcao `get_user_job_history()`)
- Modify: `backend/auth.py:577-587` (funcao `get_all_job_history()`)

**Step 1: Adicionar migration da coluna `file_size_bytes` em `init_db()`**

Em `backend/auth.py`, dentro de `init_db()`, apos o bloco de migrations de quota (linha ~131), adicionar:

```python
        # Migration: adicionar file_size_bytes na tabela job_history
        try:
            conn.execute("ALTER TABLE job_history ADD COLUMN file_size_bytes INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # coluna ja existe
```

**Step 2: Atualizar `save_job_history()` para salvar `file_size_bytes`**

Em `backend/auth.py`, funcao `save_job_history()` (linha ~539). Alterar o INSERT para incluir `file_size_bytes`:

```python
def save_job_history(job_dict):
    """Salva job finalizado no historico. Expira em JOB_EXPIRY_DAYS dias."""
    from datetime import timedelta
    now = datetime.now()
    expires = (now + timedelta(days=JOB_EXPIRY_DAYS)).isoformat()
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO job_history
                    (job_id, user_email, status, total_files, total_strings,
                     translated_strings, created_at, started_at, finished_at,
                     expires_at, file_available, file_size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                    (
                        job_dict['job_id'], job_dict['user_email'], job_dict['status'],
                        job_dict.get('total_files', 0), job_dict.get('total_strings', 0),
                        job_dict.get('translated_strings', 0), job_dict.get('created_at', ''),
                        job_dict.get('started_at'), job_dict.get('finished_at'),
                        expires, job_dict.get('file_size_bytes', 0),
                    ),
                )
    except Exception as e:
        log.debug(f'[JOB_HISTORY] Erro ao salvar: {e}')
```

**Step 3: Atualizar queries de historico para incluir `file_size_bytes`**

Em `get_user_job_history()` (linha ~565), adicionar `file_size_bytes` ao SELECT:

```python
def get_user_job_history(user_email, limit=50):
    """Retorna historico de jobs de um usuario."""
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT job_id, status, total_files, total_strings, translated_strings, "
            "created_at, started_at, finished_at, expires_at, file_available, "
            "COALESCE(file_size_bytes, 0) as file_size_bytes "
            "FROM job_history WHERE user_email = ? ORDER BY created_at DESC LIMIT ?",
            (user_email, limit),
        ).fetchall()
        return [dict(r) for r in rows]
```

Em `get_all_job_history()` (linha ~577), adicionar `file_size_bytes` ao SELECT:

```python
def get_all_job_history(limit=100):
    """Retorna historico de jobs de todos os usuarios (admin)."""
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT job_id, user_email, status, total_files, total_strings, "
            "translated_strings, created_at, started_at, finished_at, "
            "expires_at, file_available, COALESCE(file_size_bytes, 0) as file_size_bytes "
            "FROM job_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
```

**Step 4: Validar sintaxe**

Run: `venv/bin/python3 -m py_compile backend/auth.py`
Expected: Sem saida (sucesso)

**Step 5: Commit**

```bash
git add backend/auth.py
git commit -m "feat: adicionar file_size_bytes na tabela job_history"
```

---

### Task 2: Funcao `expire_job_files()` e helpers de historico

**Files:**
- Modify: `backend/auth.py` (nova funcao apos `cleanup_expired_jobs()`)
- Modify: `backend/translator.py` (nova funcao `expire_job_files()`)

**Step 1: Adicionar `get_job_history_entry()` em `auth.py`**

Apos `get_all_job_history()` (~linha 587), adicionar funcao para buscar um registro individual:

```python
def get_job_history_entry(job_id):
    """Retorna um registro do historico pelo job_id, ou None."""
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT job_id, user_email, status, total_files, total_strings, "
            "translated_strings, created_at, started_at, finished_at, "
            "expires_at, file_available, COALESCE(file_size_bytes, 0) as file_size_bytes "
            "FROM job_history WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None
```

**Step 2: Adicionar `mark_job_files_expired()` em `auth.py`**

Logo apos a funcao anterior:

```python
def mark_job_files_expired(job_id):
    """Marca file_available=0 para um job especifico no historico."""
    try:
        with _db_lock:
            with _db_conn() as conn:
                conn.execute(
                    "UPDATE job_history SET file_available = 0 WHERE job_id = ?",
                    (job_id,),
                )
    except Exception as e:
        log.error(f'[JOB_HISTORY] Erro ao marcar expirado {job_id}: {e}')
```

**Step 3: Adicionar `get_user_deletable_jobs()` em `auth.py`**

Logo apos a funcao anterior. Retorna jobs do usuario que podem ser deletados (file_available=1), ordenados por tamanho:

```python
def get_user_deletable_jobs(user_email, limit=10):
    """Retorna jobs do usuario com arquivos disponiveis, maiores primeiro."""
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT job_id, COALESCE(file_size_bytes, 0) as file_size_bytes, "
            "created_at, expires_at "
            "FROM job_history WHERE user_email = ? AND file_available = 1 "
            "ORDER BY file_size_bytes DESC LIMIT ?",
            (user_email, limit),
        ).fetchall()
        now = datetime.now().isoformat()
        result = []
        for r in rows:
            d = dict(r)
            d['size_mb'] = round(d['file_size_bytes'] / (1024 * 1024), 1)
            d['expired'] = d['expires_at'] < now
            result.append(d)
        return result
```

**Step 4: Criar `expire_job_files()` em `translator.py`**

Em `backend/translator.py`, apos `delete_job()` (~linha 604), adicionar:

```python
def expire_job_files(job_id):
    """Remove arquivos de um job mas preserva historico no DB.
    Diferente de delete_job() que remove tudo, esta funcao:
    - Remove pasta jobs/{job_id}/ do disco
    - Atualiza storage_used_bytes do usuario (negativo)
    - Marca file_available=0 no job_history
    - NAO deleta registros do DB (jobs ou job_history)
    Retorna (freed_bytes, user_email) ou (0, None) se nao encontrou.
    """
    from backend.auth import get_job_history_entry, mark_job_files_expired

    # Buscar info do job (memoria > DB jobs > job_history)
    job = _get(job_id)
    file_size = job.file_size_bytes if job else 0
    user_email = job.user_email if job else None

    if not job:
        db_job = get_job_db(job_id)
        if db_job:
            file_size = db_job.get('file_size_bytes', 0)
            user_email = db_job.get('user_email')

    if not user_email:
        history = get_job_history_entry(job_id)
        if history:
            file_size = history.get('file_size_bytes', 0)
            user_email = history.get('user_email')

    if not user_email:
        log.warning(f'[{job_id}] expire_job_files: job nao encontrado')
        return 0, None

    # Remover arquivos do disco
    job_dir = os.path.join(JOBS_FOLDER, job_id)
    freed_bytes = 0
    if os.path.exists(job_dir):
        freed_bytes = _get_dir_size(job_dir)
        shutil.rmtree(job_dir, ignore_errors=True)

    # Se nao tinha tamanho no DB, usar tamanho real do disco
    if freed_bytes == 0:
        freed_bytes = file_size

    # Marcar como expirado no historico
    mark_job_files_expired(job_id)

    # Remover da tabela jobs ativa (se existir)
    delete_job_db(job_id)

    # Remover da memoria
    _pop(job_id)

    # Devolver quota
    if user_email and freed_bytes > 0:
        update_storage_used(user_email, -freed_bytes)

    log.info(f'[{job_id}] Arquivos expirados ({freed_bytes / (1024*1024):.1f} MB liberados)')
    return freed_bytes, user_email
```

**Step 5: Atualizar import em `translator.py`**

Em `backend/translator.py` linha 23, adicionar o novo import:

```python
from backend.auth import save_job_db, get_jobs_db, get_job_db, delete_job_db, update_storage_used
```

(o import ja esta correto, mas as novas funcoes `get_job_history_entry` e `mark_job_files_expired` sao importadas localmente dentro de `expire_job_files()` para evitar circular imports)

**Step 6: Validar sintaxe**

Run: `venv/bin/python3 -m py_compile backend/auth.py && venv/bin/python3 -m py_compile backend/translator.py`
Expected: Sem saida (sucesso)

**Step 7: Commit**

```bash
git add backend/auth.py backend/translator.py
git commit -m "feat: adicionar expire_job_files() e helpers de historico"
```

---

### Task 3: Cleanup Periodico (Background Thread)

**Files:**
- Modify: `backend/app.py:44-83` (area de inicializacao do app)

**Step 1: Adicionar thread de cleanup apos inicializacao do SocketIO**

Em `backend/app.py`, apos a criacao do `socketio` (linha ~83), adicionar:

```python
# ============================================================================
# Cleanup periodico (background thread)
# ============================================================================

_CLEANUP_INTERVAL = 86400  # 24 horas em segundos

def _cleanup_loop():
    """Thread daemon que roda cleanup a cada 24h."""
    import time as _time
    # Esperar 60s apos startup para o app estabilizar
    _time.sleep(60)
    while True:
        try:
            log.info('[CLEANUP] Iniciando limpeza periodica...')
            from backend.translator import expire_job_files
            total_freed = 0
            total_jobs = 0
            for expired_id in cleanup_expired_jobs():
                freed, _ = expire_job_files(expired_id)
                total_freed += freed
                total_jobs += 1
            cleanup_expired_sessions()
            if total_jobs > 0:
                log.info(f'[CLEANUP] {total_jobs} jobs expirados limpos, '
                         f'{total_freed / (1024*1024):.1f} MB liberados')
            else:
                log.info('[CLEANUP] Nenhum job expirado encontrado')
        except Exception as e:
            log.error(f'[CLEANUP] Erro na limpeza periodica: {e}')
        _time.sleep(_CLEANUP_INTERVAL)

# Iniciar thread de cleanup (daemon=True para morrer com o processo)
_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True, name='cleanup')
_cleanup_thread.start()
```

**Step 2: Atualizar `__main__` para usar `expire_job_files`**

Substituir o bloco `__main__` (linhas 864-871) para usar a nova funcao:

```python
if __name__ == '__main__':
    cleanup_old_jobs(max_age_hours=168)  # 7 dias
    cleanup_expired_sessions()
    # Limpar arquivos de jobs expirados (preserva historico)
    from backend.translator import expire_job_files
    for _expired_id in cleanup_expired_jobs():
        expire_job_files(_expired_id)
    log.info('Servidor iniciando em http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

**Step 3: Validar sintaxe**

Run: `venv/bin/python3 -m py_compile backend/app.py`
Expected: Sem saida (sucesso)

**Step 4: Testar importacao do app**

Run: `cd /home/fcs/Documents/trans-script-py && venv/bin/python3 -c "import backend.app; print('OK')"`
Expected: `OK` (sem erros)

**Step 5: Commit**

```bash
git add backend/app.py
git commit -m "feat: adicionar cleanup periodico de jobs expirados (24h)"
```

---

### Task 4: Endpoints de Delete e Quota

**Files:**
- Modify: `backend/app.py` (novos endpoints REST)
- Modify: `backend/app.py:25-34` (imports)

**Step 1: Atualizar imports em `app.py`**

Em `backend/app.py`, atualizar o bloco de imports de `backend.auth` (linhas 25-34):

```python
from backend.auth import (
    init_db, get_or_create_user, list_all_users, get_system_stats, get_user_by_id,
    generate_otp, verify_otp, send_otp_email,
    register_user, login_user,
    clear_untranslated_cache,
    log_activity, get_user_activity, get_all_activity,
    get_user_job_history, get_all_job_history,
    cleanup_expired_jobs, delete_user_account,
    get_user_quota, check_storage_available,
    get_job_db,
    get_job_history_entry, get_user_deletable_jobs,
)
```

**Step 2: Adicionar endpoint `GET /api/quota`**

Apos o bloco de historico do usuario (~linha 800), adicionar:

```python
@app.route('/api/quota')
@login_required
def user_quota():
    """Retorna quota de storage do usuario logado."""
    return jsonify(get_user_quota(session['user_email']))
```

**Step 3: Adicionar endpoint `DELETE /api/history/<job_id>`**

Logo apos:

```python
@app.route('/api/history/<job_id>', methods=['DELETE'])
@login_required
def delete_history_job(job_id):
    """Deleta arquivos de um job do historico (preserva metadados)."""
    if not _validate_job_id(job_id):
        return jsonify({'error': 'ID invalido'}), 400

    entry = get_job_history_entry(job_id)
    if not entry:
        return jsonify({'error': 'Job nao encontrado no historico'}), 404
    if entry['user_email'] != session['user_email']:
        return jsonify({'error': 'Acesso negado'}), 403
    if not entry['file_available']:
        return jsonify({'error': 'Arquivos ja foram removidos'}), 410

    from backend.translator import expire_job_files
    freed, _ = expire_job_files(job_id)
    quota = get_user_quota(session['user_email'])

    log_activity(session['user_email'], 'delete_history',
                 f'Job {job_id} ({freed / (1024*1024):.1f} MB)', request.remote_addr)
    log.info(f'{request.remote_addr} deletou historico: {job_id} ({freed / (1024*1024):.1f} MB)')

    return jsonify({
        'message': 'Arquivos removidos',
        'freed_bytes': freed,
        'freed_mb': round(freed / (1024 * 1024), 1),
        'quota': quota,
    })
```

**Step 4: Adicionar endpoint `DELETE /api/history` (bulk)**

Logo apos:

```python
@app.route('/api/history', methods=['DELETE'])
@login_required
def delete_history_bulk():
    """Deleta arquivos de todos os jobs do usuario (ou so expirados)."""
    expired_only = request.args.get('expired_only', '').lower() in ('true', '1', 'yes')

    from backend.translator import expire_job_files
    jobs = get_user_job_history(session['user_email'], limit=200)
    total_freed = 0
    deleted_count = 0

    from datetime import datetime as _dt
    now = _dt.now().isoformat()

    for j in jobs:
        if not j['file_available']:
            continue
        if expired_only and j['expires_at'] >= now:
            continue
        freed, _ = expire_job_files(j['job_id'])
        total_freed += freed
        deleted_count += 1

    quota = get_user_quota(session['user_email'])

    log_activity(session['user_email'], 'delete_history_bulk',
                 f'{deleted_count} jobs ({total_freed / (1024*1024):.1f} MB)',
                 request.remote_addr)
    log.info(f'{request.remote_addr} bulk delete: {deleted_count} jobs '
             f'({total_freed / (1024*1024):.1f} MB)')

    return jsonify({
        'message': f'{deleted_count} jobs limpos',
        'deleted_count': deleted_count,
        'freed_bytes': total_freed,
        'freed_mb': round(total_freed / (1024 * 1024), 1),
        'quota': quota,
    })
```

**Step 5: Melhorar resposta de quota excedida no upload**

Em `backend/app.py`, funcao `upload_file()`, no bloco que retorna 413 (linhas 430-438), substituir por:

```python
    # Verificar quota de storage
    if not check_storage_available(session['user_email'], file_size):
        os.remove(filepath)
        quota = get_user_quota(session['user_email'])
        deletable = get_user_deletable_jobs(session['user_email'], limit=5)
        log.warning(f'{ip} quota excedida: {quota["used_mb"]} MB / {quota["limit_mb"]} MB')
        return jsonify({
            'error': f'Cota de armazenamento excedida ({quota["used_mb"]} MB / {quota["limit_mb"]} MB). '
                     'Delete traducoes antigas para liberar espaco.',
            'quota': quota,
            'deletable_jobs': deletable,
        }), 413
```

**Step 6: Adicionar endpoint admin `POST /api/admin/reconcile-storage`**

No bloco de admin routes:

```python
@app.route('/api/admin/reconcile-storage', methods=['POST'])
@admin_required
def admin_reconcile_storage():
    """Recalcula storage_used_bytes de todos os usuarios a partir do disco."""
    from backend.auth import list_all_users, update_storage_used, _db_conn, _db_lock
    users = list_all_users()
    users_fixed = 0
    total_delta = 0

    for user in users:
        email = user['email']
        # Calcular uso real no disco
        real_bytes = 0
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT job_id FROM job_history WHERE user_email = ? AND file_available = 1",
                (email,),
            ).fetchall()
        for row in rows:
            job_dir = os.path.join(JOBS_FOLDER, row['job_id'])
            if os.path.exists(job_dir):
                from backend.translator import _get_dir_size
                real_bytes += _get_dir_size(job_dir)

        # Comparar com DB
        quota = get_user_quota(email)
        db_bytes = quota['used_bytes']
        delta = real_bytes - db_bytes

        if abs(delta) > 1024:  # Ignorar diferencas < 1KB
            with _db_lock:
                with _db_conn() as conn:
                    conn.execute(
                        "UPDATE users SET storage_used_bytes = ? WHERE email = ?",
                        (real_bytes, email),
                    )
            log.info(f'[RECONCILE] {email}: DB={db_bytes/(1024*1024):.1f}MB, '
                     f'disk={real_bytes/(1024*1024):.1f}MB, delta={delta/(1024*1024):.1f}MB')
            users_fixed += 1
            total_delta += delta

    log_activity(request.admin_email, 'admin_reconcile',
                 f'{users_fixed} usuarios corrigidos', request.remote_addr)

    return jsonify({
        'users_fixed': users_fixed,
        'total_delta_bytes': total_delta,
        'total_delta_mb': round(total_delta / (1024 * 1024), 1),
    })
```

**Step 7: Validar sintaxe e importacao**

Run: `venv/bin/python3 -m py_compile backend/app.py`
Expected: Sem saida (sucesso)

Run: `cd /home/fcs/Documents/trans-script-py && venv/bin/python3 -c "import backend.app; print('OK')"`
Expected: `OK`

**Step 8: Commit**

```bash
git add backend/app.py backend/auth.py
git commit -m "feat: endpoints de delete historico, quota dedicada, e reconciliacao admin"
```

---

### Task 5: Frontend — API Service Layer

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: Adicionar funcoes de API para historico e quota**

Apos `getActivity()` (~linha 159), adicionar:

```javascript
export async function getQuota() {
  const res = await fetch(`${API_BASE}/quota`, { credentials: 'include' })
  if (!res.ok) throw new Error('Erro ao carregar quota')
  return res.json()
}

export async function deleteHistoryJob(jobId) {
  const res = await fetch(`${API_BASE}/history/${jobId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Erro ao deletar job')
  return data
}

export async function deleteHistoryBulk(expiredOnly = false) {
  const qs = expiredOnly ? '?expired_only=true' : ''
  const res = await fetch(`${API_BASE}/history${qs}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Erro ao deletar jobs')
  return data
}
```

**Step 2: Adicionar funcao admin de reconcile**

Apos `adminDeleteUser()` (~linha 215), adicionar:

```javascript
export async function adminReconcileStorage(token) {
  const res = await fetch(`${API_BASE}/admin/reconcile-storage`, {
    method: 'POST',
    credentials: 'include',
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Erro ao reconciliar storage')
  return data
}
```

**Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: adicionar funcoes de API para historico, quota e reconcile"
```

---

### Task 6: Frontend — UserHistory com Quota e Delete

**Files:**
- Modify: `frontend/src/components/UserHistory.jsx`

**Step 1: Reescrever UserHistory.jsx com barra de quota e botoes delete**

Substituir todo o conteudo de `frontend/src/components/UserHistory.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react'
import { getHistory, getActivity, getQuota, getDownloadUrl, getVoipnowDownloadUrl, deleteHistoryJob, deleteHistoryBulk } from '../services/api'
import { timeAgo, expiresIn, ACTION_LABELS } from '../utils/formatters'

function QuotaBar({ quota }) {
  if (!quota) return null
  const pct = quota.percent || 0
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-yellow-500' : 'bg-green-500'
  const textColor = pct >= 90 ? 'text-red-400' : pct >= 70 ? 'text-yellow-400' : 'text-gray-400'

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400">Armazenamento</span>
        <span className={textColor}>
          {quota.used_mb} MB / {quota.limit_mb} MB ({pct}%)
        </span>
      </div>
      <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  )
}

export default function UserHistory({ onBack }) {
  const [tab, setTab] = useState('jobs')
  const [jobs, setJobs] = useState([])
  const [activity, setActivity] = useState([])
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null) // job_id sendo deletado
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [confirmBulk, setConfirmBulk] = useState(false)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([getHistory(), getActivity(), getQuota()])
      .then(([j, a, q]) => { setJobs(j); setActivity(a); setQuota(q) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleDeleteJob = async (jobId) => {
    if (deleting) return
    setDeleting(jobId)
    try {
      const result = await deleteHistoryJob(jobId)
      setQuota(result.quota)
      setJobs(prev => prev.map(j =>
        j.job_id === jobId ? { ...j, file_available: 0 } : j
      ))
    } catch {
      // silencioso
    } finally {
      setDeleting(null)
    }
  }

  const handleBulkDelete = async (expiredOnly) => {
    setBulkDeleting(true)
    setConfirmBulk(false)
    try {
      const result = await deleteHistoryBulk(expiredOnly)
      setQuota(result.quota)
      loadData() // recarregar tudo
    } catch {
      // silencioso
    } finally {
      setBulkDeleting(false)
    }
  }

  const hasAvailableFiles = jobs.some(j => j.file_available)

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="inline-block w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm mt-3">Carregando historico...</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-gray-500 hover:text-gray-300 text-sm flex items-center gap-1.5 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Voltar
        </button>
        <h2 className="text-lg font-semibold text-gradient">Minha Conta</h2>
      </div>

      {/* Quota Bar */}
      <QuotaBar quota={quota} />

      {/* Botao liberar espaco */}
      {quota && quota.percent >= 80 && hasAvailableFiles && (
        <div className="relative">
          <button
            onClick={() => setConfirmBulk(!confirmBulk)}
            disabled={bulkDeleting}
            className="w-full text-sm py-2 px-3 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
          >
            {bulkDeleting ? 'Liberando espaco...' : 'Liberar espaco'}
          </button>
          {confirmBulk && (
            <div className="absolute top-full left-0 right-0 mt-1 glass-light rounded-lg p-3 z-10 space-y-2">
              <p className="text-xs text-gray-400">O que deseja remover?</p>
              <button
                onClick={() => handleBulkDelete(true)}
                className="w-full text-xs py-1.5 px-3 rounded bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition-colors"
              >
                Apenas expirados
              </button>
              <button
                onClick={() => handleBulkDelete(false)}
                className="w-full text-xs py-1.5 px-3 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Todos os arquivos
              </button>
              <button
                onClick={() => setConfirmBulk(false)}
                className="w-full text-xs py-1.5 px-3 rounded text-gray-500 hover:text-gray-300 transition-colors"
              >
                Cancelar
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 glass-light rounded-lg p-1">
        <button
          onClick={() => setTab('jobs')}
          className={`flex-1 text-sm py-2 rounded-md transition-all ${
            tab === 'jobs' ? 'bg-accent-500/20 text-accent-400 font-medium' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Traducoes ({jobs.length})
        </button>
        <button
          onClick={() => setTab('activity')}
          className={`flex-1 text-sm py-2 rounded-md transition-all ${
            tab === 'activity' ? 'bg-accent-500/20 text-accent-400 font-medium' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Atividade ({activity.length})
        </button>
      </div>

      {/* Job History */}
      {tab === 'jobs' && (
        <div className="space-y-2">
          {jobs.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-6">Nenhuma traducao ainda.</p>
          ) : jobs.map((j) => {
            const expired = new Date(j.expires_at) < new Date()
            const sizeMb = j.file_size_bytes ? (j.file_size_bytes / (1024 * 1024)).toFixed(1) : null
            return (
              <div key={j.job_id} className="glass-light rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      j.status === 'completed' ? 'bg-green-400' :
                      j.status === 'failed' ? 'bg-red-400' :
                      j.status === 'cancelled' ? 'bg-yellow-400' : 'bg-gray-400'
                    }`} />
                    <span className="text-sm text-gray-200 font-mono">#{j.job_id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      j.status === 'completed' ? 'bg-green-500/10 text-green-400' :
                      j.status === 'failed' ? 'bg-red-500/10 text-red-400' :
                      'bg-yellow-500/10 text-yellow-400'
                    }`}>
                      {j.status === 'completed' ? 'Concluido' : j.status === 'failed' ? 'Falhou' : 'Cancelado'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">{timeAgo(j.created_at)}</span>
                    {j.file_available ? (
                      <button
                        onClick={() => handleDeleteJob(j.job_id)}
                        disabled={deleting === j.job_id}
                        className="text-gray-600 hover:text-red-400 transition-colors disabled:opacity-50"
                        title="Remover arquivos"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    ) : (
                      <span className="text-xs text-gray-600">Removido</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>{j.total_files} arquivo{j.total_files !== 1 ? 's' : ''}</span>
                  <span>{j.translated_strings}/{j.total_strings} strings</span>
                  {sizeMb && <span>{sizeMb} MB</span>}
                  {j.file_available ? (
                    <span className={expired ? 'text-red-400' : 'text-gray-500'}>
                      {expired ? 'Expirado' : `Expira em ${expiresIn(j.expires_at)}`}
                    </span>
                  ) : (
                    <span className="text-gray-600">Arquivos removidos</span>
                  )}
                </div>

                {j.status === 'completed' && j.file_available && !expired && (
                  <div className="flex items-center gap-3">
                    <a
                      href={getDownloadUrl(j.job_id)}
                      className="inline-flex items-center gap-1.5 text-xs text-accent-400 hover:text-accent-300 transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Baixar ZIP
                    </a>
                    <a
                      href={getVoipnowDownloadUrl(j.job_id)}
                      className="inline-flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Baixar VoipNow
                    </a>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Activity Log */}
      {tab === 'activity' && (
        <div className="space-y-1">
          {activity.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-6">Nenhuma atividade registrada.</p>
          ) : activity.map((a, i) => (
            <div key={i} className="glass-light rounded-lg px-4 py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-200 font-medium min-w-[80px]">
                  {ACTION_LABELS[a.action] || a.action}
                </span>
                {a.details && (
                  <span className="text-xs text-gray-500 truncate max-w-[180px]">{a.details}</span>
                )}
              </div>
              <span className="text-xs text-gray-600 shrink-0">{timeAgo(a.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/UserHistory.jsx
git commit -m "feat: UserHistory com barra de quota, delete individual e em massa"
```

---

### Task 7: Frontend — Bloqueio de Upload por Quota

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Adicionar bloqueio visual de upload quando quota >= 100%**

Em `frontend/src/App.jsx`, a variavel `user` ja contem `quota` (vindo de `/api/auth/me`, linha 327 de app.py). O bloqueio sera feito no componente principal.

Dentro do bloco `{page === 'main' && ( ... )}` (~linha 159), antes de `{showUpload && ( ... )}` (~linha 192), adicionar verificacao de quota:

Substituir o bloco:

```jsx
                {showUpload && (
                  <FileUpload onUpload={handleUpload} disabled={false} />
                )}
```

Por:

```jsx
                {showUpload && user?.quota?.percent >= 100 ? (
                  <div className="text-center py-6 space-y-3">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-500/10">
                      <svg className="w-6 h-6 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                      </svg>
                    </div>
                    <p className="text-sm text-red-400 font-medium">
                      Armazenamento cheio ({user.quota.used_mb} MB / {user.quota.limit_mb} MB)
                    </p>
                    <p className="text-xs text-gray-500">
                      Delete traducoes antigas para liberar espaco.
                    </p>
                    <button
                      onClick={() => setPage('history')}
                      className="text-sm text-accent-400 hover:text-accent-300 transition-colors"
                    >
                      Gerenciar historico
                    </button>
                  </div>
                ) : showUpload ? (
                  <FileUpload onUpload={handleUpload} disabled={false} />
                ) : null}
```

**Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: bloquear upload quando quota de storage esta cheia"
```

---

### Task 8: Frontend — Botao Reconcile no Admin Panel

**Files:**
- Modify: `frontend/src/pages/AdminPanel.jsx`

**Step 1: Ler o AdminPanel atual**

Ler `frontend/src/pages/AdminPanel.jsx` para entender a estrutura e onde adicionar o botao.

**Step 2: Adicionar botao de reconciliacao na aba de estatisticas ou configuracoes**

Importar `adminReconcileStorage` de `../services/api`. Adicionar botao na secao de estatisticas/admin do painel:

```jsx
// Dentro do painel admin, na secao de ferramentas ou stats:
const [reconciling, setReconciling] = useState(false)
const [reconcileResult, setReconcileResult] = useState(null)

const handleReconcile = async () => {
  setReconciling(true)
  setReconcileResult(null)
  try {
    const result = await adminReconcileStorage(token)
    setReconcileResult(result)
  } catch (err) {
    setReconcileResult({ error: err.message })
  } finally {
    setReconciling(false)
  }
}

// No JSX:
<button
  onClick={handleReconcile}
  disabled={reconciling}
  className="text-xs px-3 py-1.5 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors disabled:opacity-50"
>
  {reconciling ? 'Reconciliando...' : 'Reconciliar Storage'}
</button>
{reconcileResult && !reconcileResult.error && (
  <span className="text-xs text-green-400 ml-2">
    {reconcileResult.users_fixed} usuarios corrigidos ({reconcileResult.total_delta_mb} MB)
  </span>
)}
{reconcileResult?.error && (
  <span className="text-xs text-red-400 ml-2">{reconcileResult.error}</span>
)}
```

**Nota:** A implementacao exata depende da estrutura do AdminPanel. Ler o arquivo primeiro, depois integrar o botao na secao mais apropriada.

**Step 3: Commit**

```bash
git add frontend/src/pages/AdminPanel.jsx
git commit -m "feat: botao reconciliar storage no painel admin"
```

---

### Task 9: Build do Frontend e Teste Integrado

**Step 1: Build do frontend**

Run: `cd /home/fcs/Documents/trans-script-py/frontend && npm run build`
Expected: Build com sucesso, sem erros

**Step 2: Verificar sintaxe de todos os arquivos Python**

Run:
```bash
cd /home/fcs/Documents/trans-script-py
venv/bin/python3 -m py_compile backend/auth.py
venv/bin/python3 -m py_compile backend/translator.py
venv/bin/python3 -m py_compile backend/app.py
```
Expected: Sem saida (sucesso)

**Step 3: Verificar importacao do app**

Run: `cd /home/fcs/Documents/trans-script-py && venv/bin/python3 -c "import backend.app; print('OK')"`
Expected: `OK`

**Step 4: Commit build**

```bash
git add backend/static/
git commit -m "build: frontend compilado com historico e quota"
```

---

### Task 10: Teste Manual E2E

**Step 1: Iniciar o servidor**

Run: `cd /home/fcs/Documents/trans-script-py && venv/bin/python3 -m backend.app`

**Step 2: Verificar no navegador**

1. Login na aplicacao
2. Ir para "Minha Conta" — verificar barra de quota
3. Ver historico de jobs — verificar tamanho (MB) e botao delete
4. Clicar em delete de um job — verificar que quota atualiza
5. Fazer upload de arquivo — verificar que quota e verificada
6. No admin panel — verificar botao "Reconciliar Storage"

**Step 3: Verificar logs do cleanup**

Verificar nos logs do servidor:
```
[CLEANUP] Iniciando limpeza periodica...
[CLEANUP] N jobs expirados limpos, X MB liberados
```
(aparecera 60s apos iniciar o servidor)

**Step 4: Commit final se houver ajustes**

```bash
git add -A
git commit -m "fix: ajustes finais do teste E2E"
```
