export interface Clip {
  id: string
  job_id: string
  clip_index: number
  score: number
  duration: number
  transcript: string
  has_face: boolean
  emotion: string | null
  primary_type: string
  tags: string[]
  video_url: string
  thumbnail_url: string
  source_title: string
  start_time: number
  end_time: number
}
