import type { Clip } from '../../types/clip'
import ClipCard from './ClipCard'

interface Props {
  clips: Clip[]
}

export default function ClipsGrid({ clips }: Props) {
  if (clips.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500">
        <p>No clips yet.</p>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {clips.map(clip => (
        <ClipCard key={clip.id} clip={clip} />
      ))}
    </div>
  )
}
