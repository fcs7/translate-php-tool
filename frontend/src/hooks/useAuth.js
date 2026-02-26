import { useState, useEffect, useCallback } from 'react'
import { getMe, logout as apiLogout } from '../services/api'

export function useAuth() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    try {
      const data = await getMe()
      setUser(data.user)
    } catch {
      setUser(null)
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
  }, [])

  return {
    user,
    loading,
    isAuthenticated: !!user,
    logout,
    refetch: fetchMe,
  }
}
