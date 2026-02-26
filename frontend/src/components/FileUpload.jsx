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
          border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
          transition-all duration-200
          ${dragActive
            ? 'border-blue-500 bg-blue-500/10'
            : 'border-gray-700 hover:border-gray-500 bg-gray-900/50'
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
          <div className="space-y-2">
            <div className="text-4xl">📦</div>
            <p className="text-white font-medium">{file.name}</p>
            <p className="text-gray-400 text-sm">{formatSize(file.size)}</p>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setFile(null)
                if (inputRef.current) inputRef.current.value = ''
              }}
              className="text-red-400 text-sm hover:text-red-300"
            >
              Remover
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-4xl">📁</div>
            <p className="text-gray-300">
              Arraste um arquivo <span className="text-blue-400 font-mono">.zip</span> <span className="text-blue-400 font-mono">.rar</span> ou <span className="text-blue-400 font-mono">.tar</span> aqui
            </p>
            <p className="text-gray-500 text-sm">ou clique para selecionar</p>
          </div>
        )}
      </div>

      {/* Configuracao de delay */}
      <div className="flex items-center gap-4 bg-gray-900/50 rounded-lg p-4 border border-gray-800">
        <label className="text-sm text-gray-400 whitespace-nowrap">
          Delay (s):
        </label>
        <input
          type="range"
          min="0.05"
          max="2"
          step="0.05"
          value={delay}
          onChange={(e) => setDelay(parseFloat(e.target.value))}
          className="flex-1 accent-blue-500"
          disabled={disabled}
        />
        <span className="text-sm text-white font-mono w-12 text-right">
          {delay.toFixed(2)}
        </span>
      </div>

      {/* Erro */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Botao de enviar */}
      <button
        onClick={handleSubmit}
        disabled={!file || uploading || disabled}
        className={`
          w-full py-3 rounded-lg font-medium text-sm transition-all
          ${file && !uploading && !disabled
            ? 'bg-blue-600 hover:bg-blue-500 text-white'
            : 'bg-gray-800 text-gray-500 cursor-not-allowed'
          }
        `}
      >
        {uploading ? 'Enviando...' : 'Iniciar Traducao'}
      </button>
    </div>
  )
}
