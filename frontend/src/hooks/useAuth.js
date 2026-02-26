import { useState, useEffect, useCallback } from 'react'
import { getMe, logout as apiLogout } from '../services/api'
import { getCache, setCache, clearAllCache } from '../services/cache'

// Dados não-sensíveis do usuário (id, email) — seguro guardar no localStorage
const USER_KEY = 'user'
const USER_TTL = 5 * 60 * 1000 // 5 minutos

export function useAuth() {
  // Stale-while-revalidate: inicia com dados em cache para exibição imediata,
  // e valida a sessão no servidor em background sem mostrar spinner.
  const [user, setUser] = useState(() => getCache(USER_KEY))
  const [loading, setLoading] = useState(() => getCache(USER_KEY) === null)

  const fetchMe = useCallback(async () => {
    try {
      const data = await getMe()
      setUser(data.user)
      setCache(USER_KEY, data.user, USER_TTL)
    } catch {
      // Sessão expirada ou inválida — descarta cache e exige novo login
      setUser(null)
      clearAllCache()
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // ignora erro de rede
    }
    setUser(null)
    clearAllCache()
  }, [])

  return {
    user,
    loading,
    isAuthenticated: !!user,
    logout,
    refetch: fetchMe,
  }
}
