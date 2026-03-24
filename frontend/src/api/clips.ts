import type { Clip } from '../types/clip'
import client from './client'

export const fetchJobClips = (jobId: string): Promise<Clip[]> =>
  client.get<Clip[]>(`/api/jobs/${jobId}/clips`).then(r => r.data)
