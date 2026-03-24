import { useEffect, useRef } from 'react'

interface Props {
  logs: string[]
  className?: string
}

export default function LogViewer({ logs, className = '' }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className={`bg-[#0d0e1f] rounded-xl border border-[#2a2d4a] overflow-y-auto font-mono text-xs text-slate-300 p-4 ${className}`}>
      {logs.length === 0 ? (
        <p className="text-slate-500 italic">Waiting for logs...</p>
      ) : (
        logs.map((line, i) => {
          const isError = line.includes('ERROR')
          const isWarn = line.includes('WARNING')
          return (
            <div
              key={i}
              className={`leading-5 whitespace-pre-wrap break-all ${
                isError ? 'text-red-400' : isWarn ? 'text-yellow-400' : 'text-slate-300'
              }`}
            >
              {line}
            </div>
          )
        })
      )}
      <div ref={bottomRef} />
    </div>
  )
}
