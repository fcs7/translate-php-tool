import { useState, useRef, useEffect, useCallback } from 'react'
import { requestOtp, verifyOtp } from '../services/api'

export default function LoginPage({ onSuccess }) {
  const [step, setStep] = useState('email')   // 'email' | 'otp'
  const [email, setEmail] = useState('')
  const [digits, setDigits] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resendCountdown, setResendCountdown] = useState(0)

  const emailRef = useRef(null)
  const digitRefs = useRef([])
  const countdownRef = useRef(null)

  // Foca o input de e-mail ao montar
  useEffect(() => {
    emailRef.current?.focus()
  }, [])

  // Timer de reenvio
  const startCountdown = useCallback((seconds = 60) => {
    setResendCountdown(seconds)
    clearInterval(countdownRef.current)
    countdownRef.current = setInterval(() => {
      setResendCountdown(prev => {
        if (prev <= 1) {
          clearInterval(countdownRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }, [])

  useEffect(() => () => clearInterval(countdownRef.current), [])

  // ─── Passo 1: Enviar OTP ──────────────────────────────────────────────────

  function isValidEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
  }

  async function handleRequestOtp(e) {
    e.preventDefault()
    setError('')

    if (!isValidEmail(email)) {
      setError('Digite um e-mail valido.')
      return
    }

    setLoading(true)
    try {
      await requestOtp(email)
      setStep('otp')
      startCountdown(60)
      setTimeout(() => digitRefs.current[0]?.focus(), 50)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ─── Passo 2: Inputs OTP ─────────────────────────────────────────────────

  function handleDigitChange(index, value) {
    const digit = value.replace(/\D/g, '').slice(-1)
    const next = [...digits]
    next[index] = digit
    setDigits(next)
    setError('')

    if (digit && index < 5) {
      digitRefs.current[index + 1]?.focus()
    }
  }

  function handleDigitKeyDown(index, e) {
    if (e.key === 'Backspace') {
      if (digits[index]) {
        const next = [...digits]
        next[index] = ''
        setDigits(next)
      } else if (index > 0) {
        digitRefs.current[index - 1]?.focus()
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      digitRefs.current[index - 1]?.focus()
    } else if (e.key === 'ArrowRight' && index < 5) {
      digitRefs.current[index + 1]?.focus()
    }
  }

  function handlePaste(e) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    const next = ['', '', '', '', '', '']
    for (let i = 0; i < pasted.length; i++) next[i] = pasted[i]
    setDigits(next)
    setError('')
    const focusIdx = Math.min(pasted.length, 5)
    digitRefs.current[focusIdx]?.focus()
  }

  // ─── Passo 2: Verificar OTP ───────────────────────────────────────────────

  async function handleVerifyOtp(e) {
    e.preventDefault()
    setError('')

    const code = digits.join('')
    if (code.length < 6) {
      setError('Digite todos os 6 digitos.')
      return
    }

    setLoading(true)
    try {
      const data = await verifyOtp(email, code)
      onSuccess(data.user)
    } catch (err) {
      setError(err.message)
      setDigits(['', '', '', '', '', ''])
      setTimeout(() => digitRefs.current[0]?.focus(), 50)
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    if (resendCountdown > 0) return
    setError('')
    setDigits(['', '', '', '', '', ''])
    setLoading(true)
    try {
      await requestOtp(email)
      startCountdown(60)
      setTimeout(() => digitRefs.current[0]?.focus(), 50)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4">

      {/* Logo */}
      <div className="flex items-center gap-3 mb-10">
        <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center
                        text-xl font-bold text-white select-none">
          T
        </div>
        <div>
          <p className="text-white font-semibold text-lg leading-none">Trans-Script</p>
          <p className="text-gray-500 text-xs mt-0.5">Tradutor PHP · EN → PT-BR</p>
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-sm bg-gray-900 border border-gray-800 rounded-2xl
                      shadow-2xl overflow-hidden">

        {step === 'email' ? (

          /* ── Passo 1: E-mail ─────────────────────────────────────── */
          <form onSubmit={handleRequestOtp} className="p-8 space-y-6">
            <div>
              <h1 className="text-xl font-semibold text-white">Entrar ou cadastrar-se
                
              </h1>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-gray-400">E-mail</label>
              <input
                ref={emailRef}
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setError('') }}
                placeholder="Digite seu e-mail"
                autoComplete="email"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5
                           text-white placeholder-gray-600 text-sm outline-none
                           focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                           transition-colors"
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-2.5 rounded-lg font-medium text-sm transition-all
                         bg-blue-600 hover:bg-blue-500 text-white
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Enviando...' : 'Continuar com e-mail →'}
            </button>
          </form>

        ) : (

          /* ── Passo 2: OTP ────────────────────────────────────────── */
          <form onSubmit={handleVerifyOtp} className="p-8 space-y-6">
            <div>
              <button
                type="button"
                onClick={() => { setStep('email'); setError(''); setDigits(['','','','','','']) }}
                className="text-gray-500 hover:text-gray-300 text-sm mb-4 flex items-center gap-1
                           transition-colors"
              >
                ← Voltar
              </button>
              <h1 className="text-xl font-semibold text-white">Verifique seu e-mail</h1>
              <p className="text-sm text-gray-400 mt-1">
                Enviamos um codigo para{' '}
                <span className="text-white">{email}</span>
              </p>
            </div>

            {/* Inputs de 6 digitos */}
            <div className="flex gap-2 justify-center" onPaste={handlePaste}>
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={el => (digitRefs.current[i] = el)}
                  type="text"
                  inputMode="numeric"
                  maxLength={2}
                  value={d}
                  onChange={e => handleDigitChange(i, e.target.value)}
                  onKeyDown={e => handleDigitKeyDown(i, e)}
                  className={`
                    w-11 h-13 text-center text-xl font-bold rounded-lg border
                    bg-gray-800 text-white outline-none transition-all
                    ${d
                      ? 'border-blue-500 ring-1 ring-blue-500/30'
                      : 'border-gray-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30'
                    }
                    ${i === 2 ? 'mr-2' : ''}
                  `}
                  style={{ width: '2.75rem', height: '3.25rem' }}
                />
              ))}
            </div>

            {error && (
              <p className="text-red-400 text-sm text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading || digits.join('').length < 6}
              className="w-full py-2.5 rounded-lg font-medium text-sm transition-all
                         bg-blue-600 hover:bg-blue-500 text-white
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Verificando...' : 'Verificar'}
            </button>

            {/* Reenviar */}
            <div className="text-center">
              <button
                type="button"
                onClick={handleResend}
                disabled={resendCountdown > 0 || loading}
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors
                           disabled:cursor-default disabled:hover:text-gray-500"
              >
                {resendCountdown > 0
                  ? `Reenviar codigo (${String(Math.floor(resendCountdown / 60)).padStart(2, '0')}:${String(resendCountdown % 60).padStart(2, '0')})`
                  : 'Reenviar codigo'}
              </button>
            </div>
          </form>

        )}
      </div>

    </div>
  )
}
