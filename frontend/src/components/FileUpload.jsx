import { useState, useRef } from 'react'

export default function FileUpload({ onUpload, disabled }) {
  const [mode, setMode] = useState('archive')  // 'archive' | 'files' | 'folder'
  const [dragActive, setDragActive] = useState(false)
  const [file, setFile] = useState(null)        // single archive
  const [files, setFiles] = useState([])         // multiple PHP files
  const [delay, setDelay] = useState(0.2)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)
  const filesRef = useRef(null)
  const folderRef = useRef(null)

  const ARCHIVE_EXTS = ['.zip', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2']

  function resetSelection() {
    setFile(null)
    setFiles([])
    setError('')
    if (inputRef.current) inputRef.current.value = ''
    if (filesRef.current) filesRef.current.value = ''
    if (folderRef.current) folderRef.current.value = ''
  }

  function switchMode(newMode) {
    resetSelection()
    setMode(newMode)
  }

  // ─── Drag & Drop ───────────────────────────────────────────────────────────

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

    const dropped = Array.from(e.dataTransfer.files)
    if (!dropped.length) return

    if (mode === 'archive') {
      const f = dropped[0]
      const name = f?.name.toLowerCase() || ''
      if (f && ARCHIVE_EXTS.some(ext => name.endsWith(ext))) {
        setFile(f)
      } else {
        setError('Formatos aceitos: ZIP, RAR, TAR, TAR.GZ')
      }
    } else {
      // files or folder mode: accept .php files from drop
      const phpFiles = dropped.filter(f => f.name.toLowerCase().endsWith('.php'))
      if (phpFiles.length > 0) {
        setFiles(phpFiles)
      } else {
        setError('Nenhum arquivo .php encontrado')
      }
    }
  }

  // ─── File selection ────────────────────────────────────────────────────────

  function handleArchiveSelect(e) {
    setError('')
    const selected = e.target.files[0]
    if (selected) setFile(selected)
  }

  function handleFilesSelect(e) {
    setError('')
    const selected = Array.from(e.target.files).filter(f =>
      f.name.toLowerCase().endsWith('.php')
    )
    if (selected.length > 0) {
      setFiles(selected)
    } else {
      setError('Nenhum arquivo .php selecionado')
    }
  }

  function handleFolderSelect(e) {
    setError('')
    const allFiles = Array.from(e.target.files)
    const phpFiles = allFiles.filter(f => f.name.toLowerCase().endsWith('.php'))
    if (phpFiles.length > 0) {
      setFiles(phpFiles)
    } else {
      setError('Nenhum arquivo .php encontrado na pasta')
    }
  }

  // ─── Submit ────────────────────────────────────────────────────────────────

  async function handleSubmit() {
    const hasContent = mode === 'archive' ? file : files.length > 0
    if (!hasContent) return
    setUploading(true)
    setError('')

    try {
      if (mode === 'archive') {
        await onUpload(file, delay)
        setFile(null)
        if (inputRef.current) inputRef.current.value = ''
      } else {
        await onUpload(files, delay)
        setFiles([])
        if (filesRef.current) filesRef.current.value = ''
        if (folderRef.current) folderRef.current.value = ''
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  // ─── Helpers ───────────────────────────────────────────────────────────────

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const totalSize = mode === 'archive'
    ? (file?.size || 0)
    : files.reduce((sum, f) => sum + f.size, 0)

  const hasContent = mode === 'archive' ? !!file : files.length > 0

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Mode selector */}
      <div className="flex gap-1 p-1 glass-light rounded-lg">
        {[
          { key: 'archive', label: 'Compactado', icon: 'M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z' },
          { key: 'files', label: 'Arquivos PHP', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8' },
          { key: 'folder', label: 'Pasta', icon: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z' },
        ].map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => switchMode(key)}
            className={`flex-1 text-xs py-2 px-3 rounded-md transition-all flex items-center justify-center gap-1.5
              ${mode === key
                ? 'bg-accent-500/20 text-accent-300 border border-accent-500/30'
                : 'text-gray-500 hover:text-gray-300 border border-transparent'
              }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d={icon} />
            </svg>
            {label}
          </button>
        ))}
      </div>

      {/* Drop zone */}
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
        onClick={() => {
          if (mode === 'archive') inputRef.current?.click()
          else if (mode === 'files') filesRef.current?.click()
          else folderRef.current?.click()
        }}
      >
        {/* Hidden inputs */}
        <input
          ref={inputRef}
          type="file"
          accept=".zip,.rar,.tar,.tar.gz,.tgz,.tar.bz2,.tbz2"
          onChange={handleArchiveSelect}
          className="hidden"
        />
        <input
          ref={filesRef}
          type="file"
          accept=".php"
          multiple
          onChange={handleFilesSelect}
          className="hidden"
        />
        <input
          ref={folderRef}
          type="file"
          /* eslint-disable-next-line react/no-unknown-property */
          webkitdirectory=""
          onChange={handleFolderSelect}
          className="hidden"
        />

        {hasContent ? (
          <div className="space-y-3">
            <div className="flex justify-center">
              {mode === 'archive' ? (
                <svg className="w-12 h-12 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                  <line x1="12" y1="22.08" x2="12" y2="12" />
                </svg>
              ) : (
                <svg className="w-12 h-12 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              )}
            </div>

            {mode === 'archive' ? (
              <p className="text-white font-medium">{file.name}</p>
            ) : (
              <p className="text-white font-medium">
                {files.length} arquivo{files.length !== 1 ? 's' : ''} .php
              </p>
            )}

            <span className="inline-flex items-center text-xs text-accent-300 bg-accent-500/10 border border-accent-500/20 rounded-full px-3 py-1 font-mono">
              {formatSize(totalSize)}
            </span>

            {/* Preview list for PHP files (max 5) */}
            {mode !== 'archive' && files.length > 0 && (
              <div className="text-left mx-auto max-w-xs">
                {files.slice(0, 5).map((f, i) => (
                  <p key={i} className="text-xs text-gray-400 truncate font-mono">
                    {f.webkitRelativePath || f.name}
                  </p>
                ))}
                {files.length > 5 && (
                  <p className="text-xs text-gray-500">...e mais {files.length - 5}</p>
                )}
              </div>
            )}

            <div>
              <button
                onClick={(e) => { e.stopPropagation(); resetSelection() }}
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
            <div className="flex justify-center">
              <svg className="w-12 h-12 text-accent-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            {mode === 'archive' ? (
              <>
                <p className="text-gray-300">
                  Arraste um arquivo <span className="text-accent-400 font-mono">.zip</span> <span className="text-accent-400 font-mono">.rar</span> ou <span className="text-accent-400 font-mono">.tar</span> aqui
                </p>
                <p className="text-gray-500 text-sm">ou clique para selecionar</p>
              </>
            ) : mode === 'files' ? (
              <>
                <p className="text-gray-300">
                  Arraste arquivos <span className="text-accent-400 font-mono">.php</span> aqui
                </p>
                <p className="text-gray-500 text-sm">ou clique para selecionar varios arquivos</p>
              </>
            ) : (
              <>
                <p className="text-gray-300">
                  Selecione uma <span className="text-accent-400">pasta</span> com arquivos <span className="text-accent-400 font-mono">.php</span>
                </p>
                <p className="text-gray-500 text-sm">clique para escolher a pasta</p>
              </>
            )}
          </div>
        )}
      </div>

      {/* Delay config */}
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

      {/* Error */}
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

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={!hasContent || uploading || disabled}
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
