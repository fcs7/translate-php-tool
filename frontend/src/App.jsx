import { useState, useCallback, useEffect, useRef } from 'react'
import Header from './components/Header'
import FileUpload from './components/FileUpload'
import TranslationProgress from './components/TranslationProgress'
import LoginPage from './pages/LoginPage'
import { useSocket } from './hooks/useSocket'
import { useAuth } from './hooks/useAuth'
import { uploadZip, cancelJob, deleteJob, getJobs, getJobStatus, clearUntranslatedCache } from './services/api'

export default function App() {
  const { user, loading, isAuthenticated, logout, refetch } = useAuth()
  const [currentJobId, setCurrentJobId] = useState(null)
  const [cacheMsg, setCacheMsg] = useState(null)
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

  const handleClearCache = useCallback(async () => {
    setCacheMsg(null)
    try {
      const data = await clearUntranslatedCache()
      setCacheMsg({ ok: true, text: data.message })
    } catch (err) {
      setCacheMsg({ ok: false, text: err.message })
    }
  }, [])

  // ─── Carregando sessao ───────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center">
        <div className="shimmer w-8 h-8 border-2 border-accent-500 border-t-transparent rounded-full animate-spin" />
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
    <div className="min-h-screen bg-surface-950 flex flex-col relative">
      {/* Decorative background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="orb w-96 h-96 bg-accent-500 -top-48 -left-48" />
        <div className="orb w-80 h-80 bg-glow-cyan top-1/2 -right-40" style={{ animationDelay: '4s' }} />
        <div className="orb w-64 h-64 bg-glow-purple bottom-0 left-1/3" style={{ animationDelay: '2s' }} />
      </div>

      <Header user={user} onLogout={logout} />

      <main className="flex-1 flex items-start justify-center p-6 relative z-10">
        <div className="w-full max-w-xl space-y-6 mt-8 fade-in">

          {/* Card principal */}
          <div className="glass rounded-2xl p-6 shadow-2xl slide-up">
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gradient flex items-center gap-2">
                {showUpload ? (
                  <>
                    <svg className="w-5 h-5 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    Enviar arquivos
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="20" x2="12" y2="10" />
                      <line x1="18" y1="20" x2="18" y2="4" />
                      <line x1="6" y1="20" x2="6" y2="16" />
                    </svg>
                    Progresso
                  </>
                )}
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
                <div className="inline-block shimmer w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-gray-400 text-sm mt-3">Carregando...</p>
              </div>
            )}
          </div>

          {/* Limpar cache de traducoes falhadas */}
          {showUpload && (
            <div className="flex flex-col items-center gap-2">
              <button
                onClick={handleClearCache}
                className="glass-light text-xs text-gray-500 hover:text-gray-300 px-4 py-2 rounded-lg transition-all
                           inline-flex items-center gap-2"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                Limpar cache de traducoes falhadas
              </button>
              {cacheMsg && (
                <p className={`text-xs ${cacheMsg.ok ? 'text-green-400' : 'text-red-400'}`}>
                  {cacheMsg.text}
                </p>
              )}
            </div>
          )}

          {/* Status da conexao */}
          <div className="flex justify-center">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <div className={`status-pulse w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
              {connected ? 'Conectado' : 'Desconectado'}
            </div>
          </div>

        </div>
      </main>
    </div>
  )
}
