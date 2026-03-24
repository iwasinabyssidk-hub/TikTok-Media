import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { deleteJob } from '../../api/jobs'
import type { Job } from '../../types/job'
import JobProgressBar from './JobProgressBar'
import JobStatusBadge from './JobStatusBadge'

interface Props {
  jobs: Job[]
}

export default function JobsTable({ jobs }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const del = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  if (jobs.length === 0) {
    return (
      <div className="text-center py-16 text-slate-500">
        <div className="text-4xl mb-3">▶</div>
        <p>No jobs yet. Create your first job above.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[#2a2d4a]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#2a2d4a] text-left text-xs text-slate-500 uppercase tracking-wider">
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Channels</th>
            <th className="px-4 py-3">Clips</th>
            <th className="px-4 py-3 w-40">Progress</th>
            <th className="px-4 py-3">Created</th>
            <th className="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              className="border-b border-[#2a2d4a] last:border-0 hover:bg-[#1a1c35] cursor-pointer transition-colors"
              onClick={() => navigate(`/jobs/${job.id}`)}
            >
              <td className="px-4 py-3">
                <JobStatusBadge status={job.status} />
              </td>
              <td className="px-4 py-3 text-slate-300 max-w-[200px] truncate">
                {job.channels.join(', ')}
              </td>
              <td className="px-4 py-3 text-slate-300">
                {job.total_clips} / {job.num_clips * job.channels.length * job.videos_per_channel} est.
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <JobProgressBar progress={job.progress} className="flex-1" />
                  <span className="text-xs text-slate-400 w-8 text-right">{job.progress}%</span>
                </div>
              </td>
              <td className="px-4 py-3 text-slate-400 text-xs">
                {new Date(job.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                <button
                  className="text-xs text-red-400 hover:text-red-300 transition-colors px-2 py-1 rounded hover:bg-red-500/10"
                  onClick={() => del.mutate(job.id)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
