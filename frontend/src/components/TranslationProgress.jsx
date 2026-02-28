import { getDownloadUrl, getVoipnowDownloadUrl } from '../services/api'

export default function TranslationProgress({ job, onCancel, onDelete, onNewTranslation }) {
  if (!job) return null

  const isRunning = job.status === 'running'
  const isCompleted = job.status === 'completed'
  const isFailed = job.status === 'failed'
  const isCancelled = job.status === 'cancelled'
  const isDone = isCompleted || isFailed || isCancelled

  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className="glass-light rounded-lg px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`status-pulse w-2.5 h-2.5 rounded-full ${
            isRunning ? 'bg-accent-400' :
            isCompleted ? 'bg-green-400' :
            isFailed ? 'bg-red-400' :
            isCancelled ? 'bg-yellow-400' :
            'bg-gray-400'
          }`} />
          <span className="text-sm font-medium text-gray-200">
            {isRunning && 'Traduzindo...'}
            {isCompleted && 'Concluido'}
            {isFailed && 'Falhou'}
            {isCancelled && 'Cancelado'}
            {job.status === 'pending' && 'Aguardando...'}
          </span>
        </div>
        <span className="text-xs text-gray-500 font-mono bg-surface-800/60 border border-white/5 rounded px-2 py-0.5">
          #{job.job_id}
        </span>
      </div>

      {/* Barra de progresso */}
      <div className="w-full bg-surface-800/80 rounded-full h-3 overflow-hidden border border-white/5">
        <div
          className={`progress-glow h-full rounded-full transition-all duration-500 ${
            isCompleted ? 'bg-gradient-to-r from-green-500 to-emerald-400' :
            isFailed ? 'bg-gradient-to-r from-red-500 to-red-400' :
            'bg-gradient-to-r from-accent-600 to-accent-400'
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>
      <div className="flex justify-between items-center px-1">
        <span className="text-xs text-gray-500">{Math.round(job.progress)}%</span>
      </div>

      {/* Detalhes */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="glass-light rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <svg className="w-4 h-4 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <p className="text-gray-400 text-xs">Arquivos</p>
          </div>
          <p className="text-white font-mono text-lg">
            {job.files_done} <span className="text-gray-500">/</span> {job.total_files}
          </p>
        </div>
        <div className="glass-light rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <svg className="w-4 h-4 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="4 7 4 4 20 4 20 7" />
              <line x1="9" y1="20" x2="15" y2="20" />
              <line x1="12" y1="4" x2="12" y2="20" />
            </svg>
            <p className="text-gray-400 text-xs">Strings</p>
          </div>
          <p className="text-white font-mono text-lg">
            {job.translated_strings} <span className="text-gray-500">/</span> {job.total_strings}
          </p>
        </div>
      </div>

      {/* Arquivo atual */}
      {isRunning && job.current_file && (
        <div className="glass-light rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1.5">
            <svg className="w-3.5 h-3.5 text-accent-400 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
            <p className="text-gray-400 text-xs">Arquivo atual</p>
          </div>
          <div className="bg-surface-800/60 border border-white/5 rounded px-3 py-1.5">
            <p className="text-accent-300 font-mono text-sm truncate">
              {job.current_file}
            </p>
          </div>
        </div>
      )}

      {/* Erros */}
      {job.errors && job.errors.length > 0 && (
        <div className="glass-light border border-red-500/20 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <p className="text-red-400 text-xs font-medium">Erros:</p>
          </div>
          {job.errors.map((err, i) => (
            <p key={i} className="text-red-300 text-xs font-mono pl-6">{err}</p>
          ))}
        </div>
      )}

      {/* Validacao */}
      {isCompleted && job.validation && job.validation.stats && (
        <div className="glass-light rounded-lg p-4 space-y-3">
          <p className="text-gray-200 text-sm font-medium flex items-center gap-2">
            <svg className="w-4 h-4 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
            Validacao
          </p>
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-center">
              <div className="flex justify-center mb-1">
                <svg className="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <p className="text-green-400 font-mono text-lg font-bold">{job.validation.stats.success}</p>
              <p className="text-gray-400 text-xs">OK</p>
            </div>
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 text-center">
              <div className="flex justify-center mb-1">
                <svg className="w-5 h-5 text-yellow-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <p className="text-yellow-400 font-mono text-lg font-bold">{job.validation.stats.untranslated}</p>
              <p className="text-gray-400 text-xs">Nao traduzidas</p>
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
              <div className="flex justify-center mb-1">
                <svg className="w-5 h-5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>
              <p className="text-red-400 font-mono text-lg font-bold">{job.validation.stats.missing_placeholders}</p>
              <p className="text-gray-400 text-xs">Placeholders</p>
            </div>
          </div>
        </div>
      )}

      {/* Acoes */}
      <div className="flex gap-2 pt-1">
        {isRunning && (
          <button
            onClick={onCancel}
            className="btn-danger flex-1 py-2.5 rounded-lg text-sm font-medium transition-all
                       inline-flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            Cancelar
          </button>
        )}

        {isCompleted && (
          <>
            <a
              href={getDownloadUrl(job.job_id)}
              className="btn-success flex-1 py-2.5 rounded-lg text-sm font-medium transition-all
                         text-center inline-flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Baixar ZIP
            </a>
            <a
              href={getVoipnowDownloadUrl(job.job_id)}
              className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-purple-600/80 text-white hover:bg-purple-500 transition-all
                         text-center inline-flex items-center justify-center gap-2 border border-purple-500/30"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Baixar VoipNow
            </a>
          </>
        )}

        {isDone && (
          <>
            <button
              onClick={onNewTranslation}
              className="btn-glow flex-1 py-2.5 rounded-lg text-sm font-medium text-white transition-all
                         inline-flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Nova Traducao
            </button>
            <button
              onClick={onDelete}
              className="glass-light py-2.5 px-4 rounded-lg text-sm font-medium text-gray-400 hover:text-white
                         transition-all inline-flex items-center justify-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              Limpar
            </button>
          </>
        )}
      </div>
    </div>
  )
}
