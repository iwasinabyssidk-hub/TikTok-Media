interface Props {
  progress: number
  className?: string
}

export default function JobProgressBar({ progress, className = '' }: Props) {
  return (
    <div className={`w-full bg-[#1e2040] rounded-full h-1.5 overflow-hidden ${className}`}>
      <div
        className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-500"
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}
