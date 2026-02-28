import { useState, useEffect } from 'react'
import { getHistory, getActivity, getDownloadUrl, getVoipnowDownloadUrl } from '../services/api'
import { timeAgo, expiresIn, ACTION_LABELS } from '../utils/formatters'

export default function UserHistory({ onBack }) {
  const [tab, setTab] = useState('jobs')
  const [jobs, setJobs] = useState([])
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getHistory(), getActivity()])
      .then(([j, a]) => { setJobs(j); setActivity(a) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

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
                  <span className="text-xs text-gray-500">{timeAgo(j.created_at)}</span>
                </div>

                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>{j.total_files} arquivo{j.total_files !== 1 ? 's' : ''}</span>
                  <span>{j.translated_strings}/{j.total_strings} strings</span>
                  <span className={expired ? 'text-red-400' : 'text-gray-500'}>
                    {expired ? 'Expirado' : `Expira em ${expiresIn(j.expires_at)}`}
                  </span>
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
