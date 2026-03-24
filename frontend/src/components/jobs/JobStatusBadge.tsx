import type { JobStatus } from '../../types/job'

const STYLES: Record<JobStatus, string> = {
  queued: 'bg-slate-700 text-slate-300',
  running: 'bg-blue-600/30 text-blue-300 animate-pulse',
  completed: 'bg-emerald-600/30 text-emerald-300',
  failed: 'bg-red-600/30 text-red-300',
  cancelled: 'bg-orange-600/30 text-orange-300',
}

export default function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STYLES[status]}`}>
      {status}
    </span>
  )
}
