import { useEffect, useRef, useState } from 'react'

interface WsMessage {
  type: 'log' | 'progress' | 'status' | 'ping'
  level?: string
  message?: string
  value?: number
  status?: string
  total_clips?: number
  error?: string
}

export function useJobWebSocket(jobId: string | undefined) {
  const [logs, setLogs] = useState<string[]>([])
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!jobId) return
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${location.host}/ws/jobs/${jobId}`)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      const msg: WsMessage = JSON.parse(evt.data)
      if (msg.type === 'log' && msg.message) {
        setLogs(prev => [...prev.slice(-500), msg.message!])
      } else if (msg.type === 'progress' && msg.value !== undefined) {
        setProgress(msg.value)
      } else if (msg.type === 'status' && msg.status) {
        setStatus(msg.status)
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [jobId])

  return { logs, progress, status }
}
