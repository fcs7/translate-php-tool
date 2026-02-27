import { useState, useRef } from 'react'

export default function FileUpload({ onUpload, disabled }) {
  const [dragActive, setDragActive] = useState(false)
  const [file, setFile] = useState(null)
  const [delay, setDelay] = useState(0.2)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  function handleDrag(e) {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    setError('')

    const droppedFile = e.dataTransfer.files[0]
    const allowed = ['.zip', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2']
    const name = droppedFile?.name.toLowerCase() || ''
    if (droppedFile && allowed.some(ext => name.endsWith(ext))) {
      setFile(droppedFile)
    } else {
      setError('Formatos aceitos: ZIP, RAR, TAR, TAR.GZ')
    }
  }

  function handleFileSelect(e) {
    setError('')
    const selected = e.target.files[0]
    if (selected) {
      setFile(selected)
    }
  }

  async function handleSubmit() {
    if (!file) return
    setUploading(true)
    setError('')

    try {
      await onUpload(file, delay)
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <div className="space-y-4">
      {/* Zona de drag & drop */}
      <div
        className={`
          glass-light border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
          transition-all duration-200
          ${dragActive
            ? 'border-accent-500 bg-accent-500/10 scale-[1.02] shadow-lg shadow-accent-500/10'
            : 'border-white/10 hover:border-accent-400/40 hover:bg-surface-800/30'
          }
          ${disabled ? 'opacity-50 pointer-events-none' : ''}
        `}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".zip,.rar,.tar,.tar.gz,.tgz,.tar.bz2,.tbz2"
          onChange={handleFileSelect}
          className="hidden"
        />

        {file ? (
          <div className="space-y-3">
            {/* Package icon */}
            <div className="flex justify-center">
              <svg className="w-12 h-12 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <p className="text-white font-medium">{file.name}</p>
            <span className="inline-flex items-center text-xs text-accent-300 bg-accent-500/10 border border-accent-500/20 rounded-full px-3 py-1 font-mono">
              {formatSize(file.size)}
            </span>
            <div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setFile(null)
                  if (inputRef.current) inputRef.current.value = ''
                }}
                className="text-red-400 text-sm hover:text-red-300 transition-colors inline-flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                Remover
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Upload cloud icon */}
            <div className="flex justify-center">
              <svg className="w-12 h-12 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <p className="text-gray-300">
              Arraste um arquivo <span className="text-accent-400 font-mono">.zip</span> <span className="text-accent-400 font-mono">.rar</span> ou <span className="text-accent-400 font-mono">.tar</span> aqui
            </p>
            <p className="text-gray-500 text-sm">ou clique para selecionar</p>
          </div>
        )}
      </div>

      {/* Configuracao de delay */}
      <div className="glass-light flex items-center gap-4 rounded-lg p-4">
        <label className="text-sm text-gray-400 whitespace-nowrap flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          Delay (s):
        </label>
        <input
          type="range"
          min="0.05"
          max="2"
          step="0.05"
          value={delay}
          onChange={(e) => setDelay(parseFloat(e.target.value))}
          className="flex-1 accent-accent-500"
          disabled={disabled}
        />
        <span className="text-sm text-white font-mono w-12 text-right bg-surface-800/60 border border-white/5 rounded px-2 py-0.5">
          {delay.toFixed(2)}
        </span>
      </div>

      {/* Erro */}
      {error && (
        <div className="glass-light border border-red-500/20 rounded-lg px-4 py-3 flex items-center gap-2">
          <svg className="w-4 h-4 text-red-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Botao de enviar */}
      <button
        onClick={handleSubmit}
        disabled={!file || uploading || disabled}
        className="btn-glow w-full py-3 rounded-lg font-medium text-sm transition-all
                   text-white disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {uploading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Enviando...
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Iniciar Traducao
          </span>
        )}
      </button>
    </div>
  )
}
