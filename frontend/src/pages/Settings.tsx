import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchConfig, saveConfig } from '../api/config'
import { fetchJobs } from '../api/jobs'

const EDITABLE_KEYS: Record<string, Record<string, { label: string; type: 'number' | 'text' | 'boolean' }>> = {
  video_processing: {
    min_clip_duration: { label: 'Min clip duration (s)', type: 'number' },
    max_clip_duration: { label: 'Max clip duration (s)', type: 'number' },
    max_selected_clips_per_video: { label: 'Clips per video (default)', type: 'number' },
  },
  youtube: {
    videos_per_channel: { label: 'Videos per channel', type: 'number' },
  },
  performance: {
    whisper_model: { label: 'Whisper model', type: 'text' },
  },
}

export default function Settings() {
  const qc = useQueryClient()
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  })
  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs })
  const hasRunning = jobs.some(j => j.status === 'running')

  const [edits, setEdits] = useState<Record<string, Record<string, unknown>>>({})
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['video_processing']))

  const mutation = useMutation({
    mutationFn: saveConfig,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config'] })
      setEdits({})
    },
  })

  const getVal = (section: string, key: string) =>
    (edits[section]?.[key] ?? (config as any)?.[section]?.[key]) ?? ''

  const setVal = (section: string, key: string, value: unknown) => {
    setEdits(prev => ({
      ...prev,
      [section]: { ...prev[section], [key]: value },
    }))
  }

  const handleSave = () => {
    if (Object.keys(edits).length === 0) return
    mutation.mutate(edits)
  }

  const hasEdits = Object.keys(edits).length > 0

  if (isLoading) return <div className="text-slate-500 text-sm py-8 text-center">Loading config...</div>

  return (
    <div className="max-w-2xl space-y-4">
      {hasRunning && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-3 text-yellow-300 text-sm">
          A job is currently running. Settings cannot be saved while a job is active.
        </div>
      )}

      {Object.entries(EDITABLE_KEYS).map(([section, keys]) => {
        const isOpen = openSections.has(section)
        return (
          <div key={section} className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[#1e2040] transition-colors"
              onClick={() =>
                setOpenSections(prev => {
                  const next = new Set(prev)
                  isOpen ? next.delete(section) : next.add(section)
                  return next
                })
              }
            >
              <span className="text-sm font-semibold text-slate-200 capitalize">
                {section.replace(/_/g, ' ')}
              </span>
              <span className="text-slate-500">{isOpen ? '▲' : '▼'}</span>
            </button>

            {isOpen && (
              <div className="px-5 pb-5 space-y-4 border-t border-[#2a2d4a]">
                {Object.entries(keys).map(([key, { label, type }]) => (
                  <div key={key}>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">{label}</label>
                    {type === 'boolean' ? (
                      <input
                        type="checkbox"
                        checked={!!getVal(section, key)}
                        onChange={e => setVal(section, key, e.target.checked)}
                        className="accent-purple-500"
                      />
                    ) : (
                      <input
                        type={type}
                        value={String(getVal(section, key))}
                        onChange={e => setVal(section, key, type === 'number' ? +e.target.value : e.target.value)}
                        className="w-full bg-[#12132a] border border-[#2a2d4a] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={!hasEdits || hasRunning || mutation.isPending}
          className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {mutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
        {mutation.isSuccess && (
          <span className="text-xs text-emerald-400">Saved successfully.</span>
        )}
        {mutation.isError && (
          <span className="text-xs text-red-400">
            Error: {(mutation.error as Error).message}
          </span>
        )}
      </div>
    </div>
  )
}
