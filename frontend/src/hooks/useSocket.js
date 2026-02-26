import { useEffect, useRef, useState, useCallback } from 'react'
import { io } from 'socket.io-client'

export function useSocket() {
  const socketRef = useRef(null)
  const activeJobRef = useRef(null)
  const [jobData, setJobData] = useState(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const socket = io('/', {
      transports: ['websocket', 'polling'],
    })

    socketRef.current = socket

    socket.on('connect', () => {
      setConnected(true)
      // Rejoina a sala do job ativo ao reconectar
      if (activeJobRef.current) {
        socket.emit('join_job', { job_id: activeJobRef.current })
      }
    })

    socket.on('disconnect', () => setConnected(false))

    socket.on('translation_progress', setJobData)
    socket.on('translation_complete', setJobData)
    socket.on('translation_error', setJobData)

    return () => { socket.disconnect() }
  }, [])

  const joinJob = useCallback((newJobId) => {
    activeJobRef.current = newJobId
    if (socketRef.current?.connected) {
      socketRef.current.emit('join_job', { job_id: newJobId })
    }
  }, [])

  return { jobData, setJobData, connected, joinJob }
}
