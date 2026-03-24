import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/jobs': 'Jobs',
  '/gallery': 'Clips Gallery',
  '/settings': 'Settings',
}

export default function Layout() {
  const { pathname } = useLocation()
  const isJobDetail = pathname.startsWith('/jobs/') && pathname !== '/jobs'
  const title = isJobDetail ? 'Job Detail' : PAGE_TITLES[pathname] ?? 'TTM'

  return (
    <div className="flex h-screen overflow-hidden bg-[#12132a]">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Navbar title={title} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
