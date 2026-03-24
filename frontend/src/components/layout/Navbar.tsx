import WaveformBar from '../shared/WaveformBar'

interface Props {
  title: string
}

export default function Navbar({ title }: Props) {
  return (
    <header className="h-14 bg-[#16172a] border-b border-[#2a2d4a] flex items-center justify-between px-6 shrink-0">
      <h1 className="text-base font-semibold text-slate-100">{title}</h1>
      <div className="flex items-center gap-4">
        <WaveformBar />
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white">
          T
        </div>
      </div>
    </header>
  )
}
