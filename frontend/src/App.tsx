import { Routes, Route, NavLink } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import SchedulePage from './pages/SchedulePage'
import JobsPage from './pages/JobsPage'
import CampusPage from './pages/CampusPage'
import { MessageSquare, Calendar, Briefcase, GraduationCap, Zap, MapPin } from 'lucide-react'

const NAV = [
  { to: '/',         end: true,  icon: MessageSquare, label: 'Knowledge Q&A', sub: 'NUS RAG Chat' },
  { to: '/schedule', end: false, icon: Calendar,      label: 'Schedule Agent', sub: 'Canvas + Syllabus + Calendar' },
  { to: '/jobs',     end: false, icon: Briefcase,     label: 'Job Agent',     sub: 'Auto Search & Apply' },
  { to: '/campus',   end: false, icon: MapPin,        label: 'Campus Route',  sub: 'AI Route Planner' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-100 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-nus-blue rounded-lg flex items-center justify-center shrink-0">
              <GraduationCap size={18} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-nus-blue text-sm leading-tight">NUS Assistant</div>
              <div className="text-xs text-gray-400">Campus AI Agent</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map(({ to, end, icon: Icon, label, sub }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group ${
                  isActive ? 'bg-nus-blue text-white' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={17} className={isActive ? 'text-white' : 'text-gray-400 group-hover:text-gray-600'} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium leading-tight">{label}</div>
                    <div className={`text-xs leading-tight mt-0.5 ${isActive ? 'text-blue-200' : 'text-gray-400'}`}>{sub}</div>
                  </div>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-1.5 mb-2">
            <Zap size={11} className="text-nus-orange" />
            <span className="text-xs font-medium text-gray-500">Powered by</span>
          </div>
          {['OpenClaw Agents', 'WaveSpeed AI', 'ChromaDB RAG'].map(t => (
            <div key={t} className="text-xs text-gray-400 leading-relaxed">{t}</div>
          ))}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/"         element={<ChatPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/jobs"     element={<JobsPage />} />
          <Route path="/campus"   element={<CampusPage />} />
        </Routes>
      </main>
    </div>
  )
}
