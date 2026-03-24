import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '⬡' },
  { to: '/jobs', label: 'Jobs', icon: '▶' },
  { to: '/gallery', label: 'Clips Gallery', icon: '⊞' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 shrink-0 bg-[#16172a] border-r border-[#2a2d4a] flex flex-col min-h-screen">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-[#2a2d4a]">
        <span className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent tracking-tight">
          TTM
        </span>
        <span className="ml-2 text-xs text-slate-500">TikTok Media</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-purple-600/20 text-purple-300 font-medium'
                  : 'text-slate-400 hover:bg-[#1e2040] hover:text-slate-200'
              }`
            }
          >
            <span className="text-base leading-none">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Version */}
      <div className="px-6 py-4 text-xs text-slate-600">v1.0.0</div>
    </aside>
  )
}
