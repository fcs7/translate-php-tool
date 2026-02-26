import { useEffect, useRef, useState, useCallback } from 'react'
import { io } from 'socket.io-client'

export function useSocket(jobId) {
  const socketRef = useRef(null)
  const [jobData, setJobData] = useState(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const socket = io('/', {
      transports: ['websocket', 'polling'],
    })

    socketRef.current = socket

    socket.on('connect', () => {
      setConnected(true)
      if (jobId) {
        socket.emit('join_job', { job_id: jobId })
      }
    })

    socket.on('disconnect', () => setConnected(false))

    socket.on('translation_progress', (data) => {
      setJobData(data)
    })

    socket.on('translation_complete', (data) => {
      setJobData(data)
    })

    socket.on('translation_error', (data) => {
      setJobData(data)
    })

    return () => {
      socket.disconnect()
    }
  }, [])

  const joinJob = useCallback((newJobId) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('join_job', { job_id: newJobId })
    }
  }, [])

  return { jobData, connected, joinJob }
}
