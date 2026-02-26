import { useState, useCallback, useEffect, useRef } from 'react'
import Header from './components/Header'
import FileUpload from './components/FileUpload'
import TranslationProgress from './components/TranslationProgress'
import LoginPage from './pages/LoginPage'
import { useSocket } from './hooks/useSocket'
import { useAuth } from './hooks/useAuth'
import { uploadZip, cancelJob, deleteJob, getJobs, getJobStatus } from './services/api'

export default function App() {
  const { user, loading, isAuthenticated, logout, refetch } = useAuth()
  const [currentJobId, setCurrentJobId] = useState(null)
  const { jobData, setJobData, connected, joinJob } = useSocket()
  const hasRestoredRef = useRef(false)

  // ─── Restaurar job ativo ao autenticar ────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      hasRestoredRef.current = false
      return
    }
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    getJobs()
      .then(jobs => {
        if (!Array.isArray(jobs) || !jobs.length) return
        const sorted = [...jobs].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        // Prioriza job em execucao/pendente, depois o mais recente
        const active =
          sorted.find(j => j.status === 'running' || j.status === 'pending') ||
          sorted[0]
        if (active) {
          setCurrentJobId(active.job_id)
          setJobData(active)
          joinJob(active.job_id)
        }
      })
      .catch(() => {})
  }, [isAuthenticated, joinJob, setJobData])

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

  // ─── Handlers ────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async (file, delay) => {
    const { job_id } = await uploadZip(file, delay)
    setCurrentJobId(job_id)
    joinJob(job_id)
  }, [joinJob])

  const handleCancel = useCallback(async () => {
    if (currentJobId) {
      await cancelJob(currentJobId)
    }
  }, [currentJobId])

  const handleDelete = useCallback(async () => {
    if (currentJobId) {
      await deleteJob(currentJobId)
      setCurrentJobId(null)
      setJobData(null)
    }
  }, [currentJobId, setJobData])

  const handleNewTranslation = useCallback(() => {
    setCurrentJobId(null)
    setJobData(null)
  }, [setJobData])

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

  return (
    <div className="min-h-screen flex flex-col">
      <Header user={user} onLogout={logout} />

      <main className="flex-1 flex items-start justify-center p-6">
        <div className="w-full max-w-lg space-y-6 mt-8">

          {/* Card principal */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-2xl">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-white">
                {showUpload ? 'Enviar arquivos' : 'Progresso'}
              </h2>
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
                onDelete={handleDelete}
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
