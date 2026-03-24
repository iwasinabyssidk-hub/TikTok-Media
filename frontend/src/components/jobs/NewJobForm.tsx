import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createJob } from '../../api/jobs'

export default function NewJobForm() {
  const [channels, setChannels] = useState('')
  const [numClips, setNumClips] = useState(1)
  const [videosPerChannel, setVideosPerChannel] = useState(2)
  const [minDuration, setMinDuration] = useState(40)
  const [maxDuration, setMaxDuration] = useState(65)
  const [open, setOpen] = useState(false)

  const navigate = useNavigate()
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: createJob,
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      setOpen(false)
      navigate(`/jobs/${job.id}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const channelList = channels
      .split('\n')
      .map(c => c.trim())
      .filter(Boolean)
    if (!channelList.length) return
    mutation.mutate({
      channels: channelList,
      num_clips: numClips,
      videos_per_channel: videosPerChannel,
      min_clip_duration: minDuration,
      max_clip_duration: maxDuration,
      channels_limit: null,
    })
  }

  return (
    <div className="mb-6">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <span className="text-lg leading-none">+</span> New Job
        </button>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl p-6 space-y-5"
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-semibold text-slate-100">New Processing Job</h2>
            <button type="button" onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-300 text-xl leading-none">×</button>
          </div>

          {/* Channels */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">
              YouTube Channels <span className="text-slate-600">(one per line)</span>
            </label>
            <textarea
              value={channels}
              onChange={e => setChannels(e.target.value)}
              rows={4}
              placeholder={"@MrBeast\nLIТВИН\nhttps://youtube.com/@channel"}
              className="w-full bg-[#12132a] border border-[#2a2d4a] rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-purple-500 resize-none"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Clips per video */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Clips per video: <span className="text-purple-400 font-bold">{numClips}</span>
              </label>
              <input
                type="range" min={1} max={10} value={numClips}
                onChange={e => setNumClips(+e.target.value)}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-slate-600 mt-0.5">
                <span>1</span><span>10</span>
              </div>
            </div>

            {/* Videos per channel */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Videos per channel: <span className="text-purple-400 font-bold">{videosPerChannel}</span>
              </label>
              <input
                type="range" min={1} max={20} value={videosPerChannel}
                onChange={e => setVideosPerChannel(+e.target.value)}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-slate-600 mt-0.5">
                <span>1</span><span>20</span>
              </div>
            </div>

            {/* Min clip duration */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Min clip duration: <span className="text-blue-400 font-bold">{minDuration}s</span>
              </label>
              <input
                type="range" min={10} max={120} value={minDuration}
                onChange={e => setMinDuration(+e.target.value)}
                className="w-full accent-blue-500"
              />
            </div>

            {/* Max clip duration */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Max clip duration: <span className="text-blue-400 font-bold">{maxDuration}s</span>
              </label>
              <input
                type="range" min={10} max={180} value={maxDuration}
                onChange={e => setMaxDuration(+e.target.value)}
                className="w-full accent-blue-500"
              />
            </div>
          </div>

          {mutation.isError && (
            <p className="text-red-400 text-xs">
              Error: {(mutation.error as Error).message}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {mutation.isPending ? 'Starting...' : 'Start Job'}
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="px-4 py-2.5 rounded-xl border border-[#2a2d4a] text-slate-400 hover:text-slate-200 text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
