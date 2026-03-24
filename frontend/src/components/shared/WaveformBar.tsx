export default function WaveformBar({ className = '' }: { className?: string }) {
  const bars = [4, 8, 12, 6, 16, 10, 14, 8, 12, 6, 18, 10, 8, 14, 6, 12, 16, 8, 10, 12]
  return (
    <div className={`flex items-end gap-0.5 opacity-40 ${className}`}>
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-0.5 rounded-full bg-purple-400"
          style={{ height: `${h}px` }}
        />
      ))}
    </div>
  )
}
