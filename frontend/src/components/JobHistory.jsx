import { getDownloadUrl } from '../services/api'

const STATUS_MAP = {
  running:   { label: 'Traduzindo', color: 'bg-blue-500', text: 'text-blue-400' },
  pending:   { label: 'Aguardando', color: 'bg-yellow-500', text: 'text-yellow-400' },
  completed: { label: 'Concluido', color: 'bg-green-500', text: 'text-green-400' },
  failed:    { label: 'Falhou', color: 'bg-red-500', text: 'text-red-400' },
  cancelled: { label: 'Cancelado', color: 'bg-gray-500', text: 'text-gray-400' },
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function JobHistory({ jobs, onSelect, onDelete }) {
  if (!jobs || jobs.length === 0) return null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-2xl">
      <h2 className="text-lg font-semibold text-white mb-1">Historico</h2>
      <p className="text-sm text-gray-400 mb-4">Traducoes anteriores da sua conta</p>

      <div className="space-y-2">
        {jobs.map((job) => {
          const st = STATUS_MAP[job.status] || STATUS_MAP.pending
          const isActive = job.status === 'running' || job.status === 'pending'

          return (
            <div
              key={job.job_id}
              className="flex items-center gap-3 bg-gray-800/50 hover:bg-gray-800 rounded-lg p-3 border border-gray-700/50 transition-colors cursor-pointer group"
              onClick={() => onSelect(job)}
            >
              {/* Indicador de status */}
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${st.color} ${isActive ? 'animate-pulse' : ''}`} />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500">#{job.job_id}</span>
                  <span className={`text-xs ${st.text}`}>{st.label}</span>
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-xs text-gray-500">{formatDate(job.created_at)}</span>
                  {job.total_files > 0 && (
                    <span className="text-xs text-gray-600">
                      {job.files_done}/{job.total_files} arquivos
                    </span>
                  )}
                  {isActive && job.progress > 0 && (
                    <span className="text-xs text-blue-400">{job.progress}%</span>
                  )}
                </div>
              </div>

              {/* Acoes */}
              <div className="flex items-center gap-1 flex-shrink-0">
                {job.status === 'completed' && job.has_output && (
                  <a
                    href={getDownloadUrl(job.job_id)}
                    onClick={(e) => e.stopPropagation()}
                    className="px-2 py-1 text-xs rounded bg-green-600/20 text-green-400 hover:bg-green-600/40 transition-colors"
                    title="Baixar ZIP"
                  >
                    Baixar
                  </a>
                )}
                {!isActive && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(job.job_id)
                    }}
                    className="px-2 py-1 text-xs rounded text-gray-600 hover:bg-red-900/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                    title="Remover"
                  >
                    Remover
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
