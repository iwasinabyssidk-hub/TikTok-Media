import { useQuery } from '@tanstack/react-query'
import { fetchJobs } from '../api/jobs'
import NewJobForm from '../components/jobs/NewJobForm'
import JobsTable from '../components/jobs/JobsTable'

export default function Jobs() {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: fetchJobs,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? []
      const hasActive = jobs.some((j: { status: string }) => j.status === 'running' || j.status === 'queued')
      return hasActive ? 8000 : 30000
    },
  })

  return (
    <div className="space-y-4">
      <NewJobForm />
      {isLoading ? (
        <div className="text-center text-slate-500 py-8 text-sm">Loading jobs...</div>
      ) : (
        <JobsTable jobs={jobs} />
      )}
    </div>
  )
}
