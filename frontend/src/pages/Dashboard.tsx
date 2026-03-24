import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchJobs } from '../api/jobs'
import StatsCards from '../components/dashboard/StatsCards'
import JobStatusBadge from '../components/jobs/JobStatusBadge'
import JobProgressBar from '../components/jobs/JobProgressBar'

export default function Dashboard() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    refetchInterval: 5000,
  })

  const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued')
  const recentJobs = jobs.slice(0, 5)

  return (
    <div className="space-y-6">
      <StatsCards jobs={jobs} />

      {/* Active jobs */}
      {activeJobs.length > 0 && (
        <div className="bg-[#1a1b2e] border border-purple-500/30 rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-purple-300 mb-4 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            Active Jobs
          </h2>
          <div className="space-y-3">
            {activeJobs.map(job => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="flex items-center gap-4 p-3 rounded-xl bg-[#12132a] hover:bg-[#1e2040] transition-colors"
              >
                <JobStatusBadge status={job.status} />
                <span className="text-sm text-slate-300 flex-1 truncate">{job.channels.join(', ')}</span>
                <div className="w-32">
                  <JobProgressBar progress={job.progress} />
                </div>
                <span className="text-xs text-slate-400 w-8 text-right">{job.progress}%</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Decorative hero banner */}
      <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-[#1a1b2e] to-[#12132a] border border-[#2a2d4a] p-8">
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'radial-gradient(circle at 30% 50%, #7c3aed 0%, transparent 50%), radial-gradient(circle at 70% 50%, #2563eb 0%, transparent 50%)',
          }}
        />
        <div className="relative z-10">
          <h2 className="text-2xl font-bold text-slate-100 mb-2">TTM — TikTok Media</h2>
          <p className="text-slate-400 text-sm max-w-md mb-6">
            Automatically extract viral highlights from YouTube videos using multi-modal AI analysis.
          </p>
          <Link
            to="/jobs"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <span>+</span> Create New Job
          </Link>
        </div>
      </div>

      {/* Recent jobs */}
      {recentJobs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Recent Jobs</h2>
            <Link to="/jobs" className="text-xs text-purple-400 hover:text-purple-300">View all →</Link>
          </div>
          <div className="space-y-2">
            {recentJobs.map(job => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="flex items-center gap-3 px-4 py-3 bg-[#1a1b2e] border border-[#2a2d4a] rounded-xl hover:border-purple-500/30 transition-colors"
              >
                <JobStatusBadge status={job.status} />
                <span className="flex-1 text-sm text-slate-300 truncate">{job.channels.join(', ')}</span>
                <span className="text-xs text-slate-500">{job.total_clips} clips</span>
                <span className="text-xs text-slate-600">{new Date(job.created_at).toLocaleDateString()}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {isLoading && (
        <div className="text-center text-slate-500 py-8 text-sm">Loading...</div>
      )}
    </div>
  )
}
