const API_BASE = '/api'

export async function uploadZip(file, delay = 0.2) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('delay', delay.toString())

  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.error || 'Erro ao enviar arquivo')
  }

  return res.json()
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error('Job nao encontrado')
  return res.json()
}

export async function getJobs() {
  const res = await fetch(`${API_BASE}/jobs`)
  return res.json()
}

export async function cancelJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
  return res.json()
}

export async function deleteJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' })
  return res.json()
}

export function getDownloadUrl(jobId) {
  return `${API_BASE}/jobs/${jobId}/download`
}
