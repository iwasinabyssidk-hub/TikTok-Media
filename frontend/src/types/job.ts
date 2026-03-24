export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Job {
  id: string
  status: JobStatus
  progress: number
  channels: string[]
  num_clips: number
  videos_per_channel: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  total_clips: number
  error: string | null
  run_subdir: string | null
  logs: string[]
  report: Record<string, unknown> | null
}

export interface JobCreate {
  channels: string[]
  num_clips: number
  videos_per_channel: number
  min_clip_duration: number
  max_clip_duration: number
  channels_limit: number | null
}
