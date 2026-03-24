import type { Job, JobCreate } from '../types/job'
import client from './client'

export const fetchJobs = (): Promise<Job[]> =>
  client.get<Job[]>('/api/jobs').then(r => r.data)

export const fetchJob = (id: string): Promise<Job> =>
  client.get<Job>(`/api/jobs/${id}`).then(r => r.data)

export const createJob = (body: JobCreate): Promise<Job> =>
  client.post<Job>('/api/jobs', body).then(r => r.data)

export const deleteJob = (id: string): Promise<void> =>
  client.delete(`/api/jobs/${id}`).then(() => undefined)
