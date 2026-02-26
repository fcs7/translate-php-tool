import { useState, useCallback } from 'react'
import Header from './components/Header'
import FileUpload from './components/FileUpload'
import TranslationProgress from './components/TranslationProgress'
import { useSocket } from './hooks/useSocket'
import { uploadZip, cancelJob, deleteJob } from './services/api'

export default function App() {
  const [currentJobId, setCurrentJobId] = useState(null)
  const { jobData, connected, joinJob } = useSocket()

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
    }
  }, [currentJobId])

  const handleNewTranslation = useCallback(() => {
    setCurrentJobId(null)
  }, [])

  const showUpload = !currentJobId
  const showProgress = currentJobId && jobData

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

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

            {/* Esperando dados do WebSocket */}
            {currentJobId && !jobData && (
              <div className="text-center py-8">
                <div className="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-gray-400 text-sm mt-3">Conectando...</p>
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
