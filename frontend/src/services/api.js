const API_BASE = '/api'

// ─── Autenticacao ─────────────────────────────────────────────────────────────

export async function requestOtp(email) {
  const res = await fetch(`${API_BASE}/auth/request-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Erro ao enviar codigo')
  return data
}

export async function verifyOtp(email, code) {
  const res = await fetch(`${API_BASE}/auth/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, code }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || 'Codigo invalido')
  return data
}

export async function logout() {
  await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  })
}

export async function getMe() {
  const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
  if (!res.ok) throw new Error('Nao autenticado')
  return res.json()
}

// ─── Jobs ─────────────────────────────────────────────────────────────────────

export async function uploadZip(file, delay = 0.2) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('delay', delay.toString())

  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })

  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.error || 'Erro ao enviar arquivo')
  }

  return res.json()
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Job nao encontrado')
  return res.json()
}

export async function getJobs() {
  const res = await fetch(`${API_BASE}/jobs`, { credentials: 'include' })
  return res.json()
}

export async function cancelJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, {
    method: 'POST',
    credentials: 'include',
  })
  return res.json()
}

export async function deleteJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  return res.json()
}

export function getDownloadUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/download`
}
