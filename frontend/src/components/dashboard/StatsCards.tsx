import type { Job } from '../../types/job'

interface Props {
  jobs: Job[]
}

export default function StatsCards({ jobs }: Props) {
  const totalClips = jobs.reduce((s, j) => s + j.total_clips, 0)
  const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued').length
  const channels = [...new Set(jobs.flatMap(j => j.channels))].length
  const completedJobs = jobs.filter(j => j.status === 'completed').length

  const stats = [
    { label: 'Total Clips', value: totalClips, icon: '⊞', gradient: 'from-purple-600 to-blue-600' },
    { label: 'Active Jobs', value: activeJobs, icon: '▶', gradient: 'from-blue-600 to-cyan-600' },
    { label: 'Channels', value: channels, icon: '⬡', gradient: 'from-pink-600 to-rose-600' },
    { label: 'Completed Jobs', value: completedJobs, icon: '✓', gradient: 'from-emerald-600 to-teal-600' },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map(({ label, value, icon, gradient }) => (
        <div
          key={label}
          className="bg-[#1a1b2e] border border-[#2a2d4a] rounded-2xl p-5 flex items-center gap-4"
        >
          <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white text-lg shrink-0`}>
            {icon}
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-100">{value}</div>
            <div className="text-xs text-slate-500">{label}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
