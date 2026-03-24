import { useEffect } from 'react'
import type { Clip } from '../../types/clip'

interface Props {
  clip: Clip
  onClose: () => void
}

export default function VideoPreviewModal({ clip, onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl overflow-hidden max-w-sm w-full"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2d4a]">
          <span className="text-sm font-medium text-slate-200">
            Clip #{clip.clip_index} — {clip.duration.toFixed(0)}s
          </span>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl leading-none">×</button>
        </div>

        <video
          src={clip.video_url}
          controls
          autoPlay
          className="w-full max-h-[60vh] object-contain bg-black"
        />

        <div className="p-4 space-y-2">
          {clip.transcript && (
            <p className="text-sm text-slate-300 italic">"{clip.transcript}"</p>
          )}
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-0.5 rounded-full bg-purple-600/20 text-purple-300">
              Score: {clip.score.toFixed(1)}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-blue-600/20 text-blue-300">
              {clip.primary_type}
            </span>
            {clip.emotion && (
              <span className="px-2 py-0.5 rounded-full bg-pink-600/20 text-pink-300">
                {clip.emotion}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 truncate">{clip.source_title}</p>
          <a
            href={clip.video_url}
            download
            className="block w-full text-center py-2 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition-opacity mt-2"
          >
            Download
          </a>
        </div>
      </div>
    </div>
  )
}
