import { useQueries, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { fetchJobClips } from '../api/clips'
import { fetchJobs } from '../api/jobs'
import ClipsGrid from '../components/clips/ClipsGrid'
import type { Clip } from '../types/clip'

export default function ClipsGallery() {
  const [selectedJob, setSelectedJob] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [minScore, setMinScore] = useState(0)

  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
  })

  const completedJobs = jobs.filter(j => j.status === 'completed')

  const clipQueries = useQueries({
    queries: completedJobs.map(job => ({
      queryKey: ['job-clips', job.id],
      queryFn: () => fetchJobClips(job.id),
      enabled: job.status === 'completed',
    })),
  })

  const allClips: Clip[] = clipQueries.flatMap(q => q.data ?? [])
  const primaryTypes = ['all', ...new Set(allClips.map(c => c.primary_type))]

  const filtered = allClips.filter(clip => {
    if (selectedJob !== 'all' && clip.job_id !== selectedJob) return false
    if (filterType !== 'all' && clip.primary_type !== filterType) return false
    if (clip.score < minScore) return false
    return true
  })

  return (
    <div className="space-y-5">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Job</label>
          <select
            value={selectedJob}
            onChange={e => setSelectedJob(e.target.value)}
            className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
          >
            <option value="all">All jobs</option>
            {completedJobs.map(j => (
              <option key={j.id} value={j.id}>
                {j.channels.join(', ')} ({j.id.slice(-6)})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-500 mb-1">Type</label>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
          >
            {primaryTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Min score: <span className="text-purple-400">{minScore}</span>
          </label>
          <input
            type="range" min={0} max={100} value={minScore}
            onChange={e => setMinScore(+e.target.value)}
            className="w-32 accent-purple-500"
          />
        </div>

        <div className="ml-auto text-sm text-slate-500">
          {filtered.length} clips
        </div>
      </div>

      {completedJobs.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <div className="text-4xl mb-3">⊞</div>
          <p>No completed jobs yet. Run a job to see clips here.</p>
        </div>
      ) : (
        <ClipsGrid clips={filtered} />
      )}
    </div>
  )
}
