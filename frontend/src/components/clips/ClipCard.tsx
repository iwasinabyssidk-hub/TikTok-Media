import { useState } from 'react'
import type { Clip } from '../../types/clip'
import VideoPreviewModal from './VideoPreviewModal'

const TYPE_COLORS: Record<string, string> = {
  dialogue: 'bg-purple-600/30 text-purple-300',
  action: 'bg-blue-600/30 text-blue-300',
  reaction: 'bg-pink-600/30 text-pink-300',
  scene_reveal: 'bg-teal-600/30 text-teal-300',
  hybrid: 'bg-slate-600/30 text-slate-300',
}

interface Props {
  clip: Clip
}

export default function ClipCard({ clip }: Props) {
  const [preview, setPreview] = useState(false)

  const scoreColor =
    clip.score >= 75 ? 'from-emerald-500 to-teal-500' :
    clip.score >= 50 ? 'from-purple-500 to-blue-500' :
    'from-slate-500 to-slate-600'

  return (
    <>
      <div className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl overflow-hidden hover:border-purple-500/50 transition-colors group">
        {/* Thumbnail */}
        <div
          className="relative aspect-[9/16] bg-[#0d0e1f] cursor-pointer overflow-hidden"
          onClick={() => setPreview(true)}
        >
          {clip.thumbnail_url ? (
            <img
              src={clip.thumbnail_url}
              alt={`Clip ${clip.clip_index}`}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-600">
              <span className="text-3xl">▶</span>
            </div>
          )}
          {/* Play overlay */}
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <span className="text-white text-xl ml-1">▶</span>
            </div>
          </div>
          {/* Score badge */}
          <div className={`absolute top-2 right-2 px-2 py-0.5 rounded-full text-xs font-bold text-white bg-gradient-to-r ${scoreColor}`}>
            {clip.score.toFixed(0)}
          </div>
          {/* Duration */}
          <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/60 text-xs text-white">
            {clip.duration.toFixed(0)}s
          </div>
        </div>

        {/* Info */}
        <div className="p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[clip.primary_type] ?? TYPE_COLORS.hybrid}`}>
              {clip.primary_type}
            </span>
            {clip.emotion && (
              <span className="text-xs text-slate-500">{clip.emotion}</span>
            )}
          </div>
          {clip.transcript && (
            <p className="text-xs text-slate-400 line-clamp-2 leading-4">
              "{clip.transcript}"
            </p>
          )}
          <p className="text-xs text-slate-600 truncate" title={clip.source_title}>
            {clip.source_title}
          </p>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => setPreview(true)}
              className="flex-1 py-1.5 rounded-lg bg-purple-600/20 text-purple-300 text-xs hover:bg-purple-600/30 transition-colors"
            >
              Preview
            </button>
            <a
              href={clip.video_url}
              download
              className="flex-1 py-1.5 rounded-lg bg-[#12132a] border border-[#2a2d4a] text-slate-400 text-xs text-center hover:text-slate-200 transition-colors"
            >
              Download
            </a>
          </div>
        </div>
      </div>

      {preview && (
        <VideoPreviewModal clip={clip} onClose={() => setPreview(false)} />
      )}
    </>
  )
}
