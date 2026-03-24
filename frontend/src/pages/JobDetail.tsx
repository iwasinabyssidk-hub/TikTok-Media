import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchJob } from '../api/jobs'
import { fetchJobClips } from '../api/clips'
import { useJobWebSocket } from '../hooks/useJobWebSocket'
import JobStatusBadge from '../components/jobs/JobStatusBadge'
import JobProgressBar from '../components/jobs/JobProgressBar'
import LogViewer from '../components/shared/LogViewer'
import ClipsGrid from '../components/clips/ClipsGrid'

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const queryClient = useQueryClient()
  const { logs: wsLogs, progress: wsProgress, status: wsStatus } = useJobWebSocket(jobId)

  // When WebSocket confirms job is done — immediately invalidate caches
  // so polling stops and fresh data (clips, final status) is fetched once
  useEffect(() => {
    if (wsStatus === 'completed' || wsStatus === 'failed' || wsStatus === 'cancelled') {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job-clips', jobId] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    }
  }, [wsStatus, jobId, queryClient])

  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => fetchJob(jobId!),
    // Polling is backup only — WS handles real-time. Use 8s to reduce noise.
    // Stop polling if WS already confirmed terminal status.
    refetchInterval: (query) => {
      const s = query.state.data?.status
      if (wsStatus === 'completed' || wsStatus === 'failed' || wsStatus === 'cancelled') return false
      return s === 'running' || s === 'queued' ? 8000 : false
    },
    enabled: !!jobId,
  })

  const { data: clips = [] } = useQuery({
    queryKey: ['job-clips', jobId],
    queryFn: () => fetchJobClips(jobId!),
    enabled: !!jobId && (job?.status === 'completed' || (job?.total_clips ?? 0) > 0),
    refetchInterval: false,
  })

  if (!job) {
    return <div className="text-slate-500 text-sm py-8 text-center">Loading...</div>
  }

  const progress = wsProgress > 0 ? wsProgress : job.progress
  const status = wsStatus ?? job.status
  const logs = wsLogs.length > 0 ? wsLogs : job.logs

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/jobs" className="text-slate-500 hover:text-slate-300 text-sm">← Jobs</Link>
        <span className="text-slate-600">/</span>
        <span className="text-slate-400 text-sm font-mono">{job.id}</span>
        <JobStatusBadge status={status as any} />
      </div>

      {/* Job info card */}
      <div className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-xs text-slate-500 mb-0.5">Channels</div>
            <div className="text-slate-200">{job.channels.join(', ')}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-0.5">Clips per video</div>
            <div className="text-slate-200">{job.num_clips}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-0.5">Videos / channel</div>
            <div className="text-slate-200">{job.videos_per_channel}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-0.5">Total clips produced</div>
            <div className="text-slate-200">{job.total_clips}</div>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-slate-500">Progress</span>
            <span className="text-xs text-slate-400">{progress}%</span>
          </div>
          <JobProgressBar progress={progress} />
        </div>

        {job.error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-red-300 text-sm">
            {job.error}
          </div>
        )}
      </div>

      {/* Clips */}
      {clips.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Clips ({clips.length})
          </h2>
          <ClipsGrid clips={clips} />
        </div>
      )}

      {/* Live logs */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Live Logs
        </h2>
        <LogViewer logs={logs} className="h-80" />
      </div>
    </div>
  )
}
