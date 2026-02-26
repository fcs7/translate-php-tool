import { useState, useCallback, useEffect, useRef } from 'react'
import Header from './components/Header'
import FileUpload from './components/FileUpload'
import TranslationProgress from './components/TranslationProgress'
import JobHistory from './components/JobHistory'
import LoginPage from './pages/LoginPage'
import { useSocket } from './hooks/useSocket'
import { useAuth } from './hooks/useAuth'
import { uploadZip, cancelJob, deleteJob, getJobs, getJobStatus } from './services/api'

export default function App() {
  const { user, loading, isAuthenticated, logout, refetch } = useAuth()
  const [currentJobId, setCurrentJobId] = useState(null)
  const { jobData, setJobData, connected, joinJob } = useSocket()
  const [jobHistory, setJobHistory] = useState([])
  const hasRestoredRef = useRef(false)

  // ─── Carregar historico de jobs ───────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      const jobs = await getJobs()
      if (Array.isArray(jobs)) {
        setJobHistory(jobs)
        return jobs
      }
    } catch {
      // ignora erros de rede
    }
    return []
  }, [])

  // ─── Restaurar job ativo ao autenticar ────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      hasRestoredRef.current = false
      setJobHistory([])
      return
    }
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    fetchHistory().then(jobs => {
      if (!jobs.length) return
      // Restaura job ativo (running/pending) automaticamente
      const active = jobs.find(j => j.status === 'running' || j.status === 'pending')
      if (active) {
        setCurrentJobId(active.job_id)
        setJobData(active)
        joinJob(active.job_id)
      }
    })
  }, [isAuthenticated, joinJob, setJobData, fetchHistory])

  // ─── Polling de status como fallback ao reconectar ───────────────────────
  // - Job em estado final: polling desnecessário, para completamente.
  // - WebSocket conectado: polling de segurança a cada 30s.
  // - WebSocket desconectado: polling ativo a cada 5s.
  useEffect(() => {
    if (!currentJobId) return

    const TERMINAL = ['completed', 'failed', 'cancelled']
    if (TERMINAL.includes(jobData?.status)) return

    const poll = async () => {
      try {
        const data = await getJobStatus(currentJobId)
        setJobData(data)
      } catch {
        // ignora erros de rede
      }
    }

    poll() // busca imediata ao montar/reconectar
    const intervalId = setInterval(poll, connected ? 30_000 : 5_000)
    return () => clearInterval(intervalId)
  }, [currentJobId, connected, jobData?.status, setJobData])

  // ─── Atualizar historico quando um job termina ────────────────────────────
  useEffect(() => {
    const TERMINAL = ['completed', 'failed', 'cancelled']
    if (jobData && TERMINAL.includes(jobData.status)) {
      fetchHistory()
    }
  }, [jobData?.status, fetchHistory])

  // ─── Handlers ────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async (file, delay) => {
    const { job_id } = await uploadZip(file, delay)
    setCurrentJobId(job_id)
    joinJob(job_id)
    fetchHistory()
  }, [joinJob, fetchHistory])

  const handleCancel = useCallback(async () => {
    if (currentJobId) {
      await cancelJob(currentJobId)
    }
  }, [currentJobId])

  const handleDelete = useCallback(async (jobId) => {
    const idToDelete = jobId || currentJobId
    if (!idToDelete) return
    await deleteJob(idToDelete)
    if (idToDelete === currentJobId) {
      setCurrentJobId(null)
      setJobData(null)
    }
    fetchHistory()
  }, [currentJobId, setJobData, fetchHistory])

  const handleNewTranslation = useCallback(() => {
    setCurrentJobId(null)
    setJobData(null)
  }, [setJobData])

  const handleSelectJob = useCallback((job) => {
    setCurrentJobId(job.job_id)
    setJobData(job)
    joinJob(job.job_id)
  }, [joinJob, setJobData])

  // ─── Carregando sessao ───────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  // ─── Nao autenticado → tela de login ────────────────────────────────────
  if (!isAuthenticated) {
    return <LoginPage onSuccess={() => refetch()} />
  }

  // ─── App principal ───────────────────────────────────────────────────────
  const showUpload = !currentJobId
  const showProgress = currentJobId && jobData
  // Historico: mostra jobs que NAO sao o job ativo atual
  const historyJobs = jobHistory.filter(j => j.job_id !== currentJobId)

  return (
    <div className="min-h-screen flex flex-col">
      <Header user={user} onLogout={logout} />

      <main className="flex-1 flex items-start justify-center p-6">
        <div className="w-full max-w-lg space-y-6 mt-8">

          {/* Card principal */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-2xl">
            <div className="mb-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">
                  {showUpload ? 'Enviar arquivos' : 'Progresso'}
                </h2>
                {showProgress && (
                  <button
                    onClick={handleNewTranslation}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    Voltar
                  </button>
                )}
              </div>
              <p className="text-sm text-gray-400 mt-1">
                {showUpload
                  ? 'Envie um ZIP com seus arquivos PHP para traduzir'
                  : 'Acompanhe a traducao em tempo real'
                }
              </p>
            </div>

            {showUpload && (
              <FileUpload onUpload={handleUpload} disabled={false} />
            )}

            {showProgress && (
              <TranslationProgress
                job={jobData}
                onCancel={handleCancel}
                onDelete={() => handleDelete(currentJobId)}
                onNewTranslation={handleNewTranslation}
              />
            )}

            {/* Esperando primeiro status */}
            {currentJobId && !jobData && (
              <div className="text-center py-8">
                <div className="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-gray-400 text-sm mt-3">Carregando...</p>
              </div>
            )}
          </div>

          {/* Historico de jobs */}
          {historyJobs.length > 0 && (
            <JobHistory
              jobs={historyJobs}
              onSelect={handleSelectJob}
              onDelete={handleDelete}
            />
          )}

          {/* Status da conexao */}
          <div className="flex justify-center">
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
              {connected ? 'Conectado' : 'Desconectado'}
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}
