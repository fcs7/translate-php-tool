import { getDownloadUrl } from '../services/api'

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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            isRunning ? 'bg-blue-500 animate-pulse' :
            isCompleted ? 'bg-green-500' :
            isFailed ? 'bg-red-500' :
            'bg-yellow-500'
          }`} />
          <span className="text-sm font-medium text-gray-300">
            {isRunning && 'Traduzindo...'}
            {isCompleted && 'Concluido'}
            {isFailed && 'Falhou'}
            {isCancelled && 'Cancelado'}
            {job.status === 'pending' && 'Aguardando...'}
          </span>
        </div>
        <span className="text-xs text-gray-500 font-mono">
          #{job.job_id}
        </span>
      </div>

      {/* Barra de progresso */}
      <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isCompleted ? 'bg-green-500' :
            isFailed ? 'bg-red-500' :
            'bg-blue-500'
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {/* Detalhes */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-800">
          <p className="text-gray-500 text-xs">Arquivos</p>
          <p className="text-white font-mono">
            {job.files_done} / {job.total_files}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-800">
          <p className="text-gray-500 text-xs">Strings</p>
          <p className="text-white font-mono">
            {job.translated_strings} / {job.total_strings}
          </p>
        </div>
      </div>

      {/* Arquivo atual */}
      {isRunning && job.current_file && (
        <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-800">
          <p className="text-gray-500 text-xs mb-1">Arquivo atual</p>
          <p className="text-blue-400 font-mono text-sm truncate">
            {job.current_file}
          </p>
        </div>
      )}

      {/* Erros */}
      {job.errors && job.errors.length > 0 && (
        <div className="bg-red-900/20 border border-red-900 rounded-lg p-3 space-y-1">
          <p className="text-red-400 text-xs font-medium">Erros:</p>
          {job.errors.map((err, i) => (
            <p key={i} className="text-red-300 text-xs font-mono">{err}</p>
          ))}
        </div>
      )}

      {/* Validacao */}
      {isCompleted && job.validation && job.validation.stats && (
        <div className="bg-gray-900/50 rounded-lg p-4 border border-gray-800 space-y-2">
          <p className="text-gray-300 text-sm font-medium">Validacao</p>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="text-center">
              <p className="text-green-400 font-mono text-lg">{job.validation.stats.success}</p>
              <p className="text-gray-500">OK</p>
            </div>
            <div className="text-center">
              <p className="text-yellow-400 font-mono text-lg">{job.validation.stats.untranslated}</p>
              <p className="text-gray-500">Nao traduzidas</p>
            </div>
            <div className="text-center">
              <p className="text-red-400 font-mono text-lg">{job.validation.stats.missing_placeholders}</p>
              <p className="text-gray-500">Placeholders</p>
            </div>
          </div>
        </div>
      )}

      {/* Acoes */}
      <div className="flex gap-2">
        {isRunning && (
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg text-sm font-medium bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-900 transition-colors"
          >
            Cancelar
          </button>
        )}

        {isCompleted && (
          <a
            href={getDownloadUrl(job.job_id)}
            className="flex-1 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-500 transition-colors text-center"
          >
            Baixar ZIP
          </a>
        )}

        {isDone && (
          <>
            <button
              onClick={onNewTranslation}
              className="flex-1 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-500 transition-colors"
            >
              Nova Traducao
            </button>
            <button
              onClick={onDelete}
              className="py-2 px-4 rounded-lg text-sm font-medium bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300 transition-colors"
            >
              Limpar
            </button>
          </>
        )}
      </div>
    </div>
  )
}
