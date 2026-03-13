import { useState, useEffect } from 'react'
import axios from 'axios'
import { Calendar, RefreshCw, Bell, BookOpen, CheckCircle2, AlertCircle, Clock } from 'lucide-react'

interface Assignment {
  id: number
  course: string
  name: string
  due_at: string | null
  points: number
  gcal_synced: boolean
}

interface Announcement {
  id: number
  course: string
  title: string
  summary: string
  posted_at: string | null
  is_read: boolean
}

function DaysChip({ due_at }: { due_at: string | null }) {
  if (!due_at) return <span className="badge badge-gray">No due date</span>
  const days = Math.ceil((new Date(due_at).getTime() - Date.now()) / 86400000)
  if (days < 0) return <span className="badge badge-red">Overdue</span>
  if (days === 0) return <span className="badge badge-red">Due today</span>
  if (days <= 3) return <span className="badge badge-yellow">{days}d left</span>
  return <span className="badge badge-gray">{days}d left</span>
}

export default function CanvasPage() {
  const [token, setToken] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<any>(null)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [activeTab, setActiveTab] = useState<'assignments' | 'announcements'>('assignments')

  const fetchData = async () => {
    try {
      const [aResp, annResp] = await Promise.all([
        axios.get('/api/canvas/assignments'),
        axios.get('/api/canvas/announcements'),
      ])
      setAssignments(aResp.data)
      setAnnouncements(annResp.data)
    } catch {}
  }

  useEffect(() => { fetchData() }, [])

  const handleSync = async () => {
    if (!token.trim()) { alert('Please enter your Canvas access token'); return }
    setIsSyncing(true)
    setSyncResult(null)
    try {
      const resp = await axios.post('/api/canvas/sync', { canvas_token: token, push_to_calendar: false })
      setSyncResult(resp.data)
      await fetchData()
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Sync failed')
    } finally {
      setIsSyncing(false)
    }
  }

  const formatDate = (dt: string | null) =>
    dt ? new Date(dt).toLocaleDateString('en-SG', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'

  const urgentCount = assignments.filter(a => {
    if (!a.due_at) return false
    const d = Math.ceil((new Date(a.due_at).getTime() - Date.now()) / 86400000)
    return d >= 0 && d <= 3
  }).length

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 shrink-0">
        <h1 className="font-semibold text-gray-800 text-sm">Canvas Sync</h1>
        <p className="text-xs text-gray-400">OpenClaw canvas_agent · WaveSpeed AI summarizer</p>
      </div>

      <div className="flex-1 scrollable px-5 py-4 space-y-4">
        {/* Connect Panel */}
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-1">
            <Calendar size={14} className="text-nus-blue" />
            <h2 className="text-sm font-semibold text-gray-700">Connect to NUS Canvas</h2>
          </div>
          <p className="text-xs text-gray-400 mb-3">
            Canvas → Account → Settings → Approved Integrations → New Access Token
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSync()}
              placeholder="Paste your Canvas access token..."
              className="input text-sm flex-1"
            />
            <button onClick={handleSync} disabled={isSyncing} className="btn-primary">
              <RefreshCw size={14} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Syncing…' : 'Sync Now'}
            </button>
          </div>

          {syncResult && (
            <div className="mt-3 flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">
              <CheckCircle2 size={13} />
              <span>
                {syncResult.courses_synced} courses · {syncResult.assignments_synced} assignments · {syncResult.announcements_synced} announcements synced
                {syncResult.calendar_events_created > 0 && ` · ${syncResult.calendar_events_created} calendar events`}
              </span>
            </div>
          )}
        </div>

        {/* Stats row */}
        {(assignments.length > 0 || announcements.length > 0) && (
          <div className="grid grid-cols-3 gap-3">
            <div className="card p-3 text-center">
              <div className="text-2xl font-bold text-nus-blue">{assignments.length}</div>
              <div className="text-xs text-gray-400 mt-0.5">Assignments</div>
            </div>
            <div className="card p-3 text-center">
              <div className={`text-2xl font-bold ${urgentCount > 0 ? 'text-red-500' : 'text-gray-400'}`}>{urgentCount}</div>
              <div className="text-xs text-gray-400 mt-0.5">Due Soon</div>
            </div>
            <div className="card p-3 text-center">
              <div className="text-2xl font-bold text-nus-orange">{announcements.length}</div>
              <div className="text-xs text-gray-400 mt-0.5">Announcements</div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div>
          <div className="flex gap-1 p-1 bg-gray-100 rounded-xl w-fit mb-4">
            {([['assignments', BookOpen, 'Assignments'], ['announcements', Bell, 'Announcements']] as const).map(([key, Icon, label]) => (
              <button key={key} onClick={() => setActiveTab(key)}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeTab === key ? 'bg-white shadow-sm text-nus-blue' : 'text-gray-500 hover:text-gray-700'
                }`}>
                <Icon size={13} />
                {label}
                <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-xs ${activeTab === key ? 'bg-nus-blue text-white' : 'bg-gray-200 text-gray-500'}`}>
                  {key === 'assignments' ? assignments.length : announcements.length}
                </span>
              </button>
            ))}
          </div>

          {activeTab === 'assignments' && (
            <div className="space-y-2">
              {assignments.length === 0 ? (
                <div className="card p-10 text-center">
                  <BookOpen size={28} className="text-gray-200 mx-auto mb-2" />
                  <p className="text-sm text-gray-400">No assignments yet</p>
                  <p className="text-xs text-gray-300 mt-1">Sync Canvas above to load your schedule</p>
                </div>
              ) : (
                assignments
                  .sort((a, b) => (a.due_at ?? '9999') < (b.due_at ?? '9999') ? -1 : 1)
                  .map(a => {
                    const days = a.due_at ? Math.ceil((new Date(a.due_at).getTime() - Date.now()) / 86400000) : null
                    const urgent = days !== null && days <= 3 && days >= 0
                    return (
                      <div key={a.id} className={`card p-3.5 flex items-center gap-3 ${urgent ? 'border-red-200 bg-red-50/50' : ''}`}>
                        <div className={`w-1 self-stretch rounded-full ${days === null ? 'bg-gray-200' : days < 0 ? 'bg-gray-300' : days <= 1 ? 'bg-red-400' : days <= 3 ? 'bg-yellow-400' : 'bg-green-400'}`} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">{a.name}</div>
                          <div className="text-xs text-gray-400 mt-0.5">{a.course}</div>
                        </div>
                        <div className="text-right flex-shrink-0 space-y-1">
                          <div className="text-xs text-gray-600 font-medium">{formatDate(a.due_at)}</div>
                          <div className="flex items-center justify-end gap-1.5">
                            <DaysChip due_at={a.due_at} />
                            {a.points > 0 && <span className="badge badge-blue">{a.points}pts</span>}
                            {a.gcal_synced && <span className="badge badge-green">GCal</span>}
                          </div>
                        </div>
                      </div>
                    )
                  })
              )}
            </div>
          )}

          {activeTab === 'announcements' && (
            <div className="space-y-3">
              {announcements.length === 0 ? (
                <div className="card p-10 text-center">
                  <Bell size={28} className="text-gray-200 mx-auto mb-2" />
                  <p className="text-sm text-gray-400">No announcements yet</p>
                  <p className="text-xs text-gray-300 mt-1">Sync Canvas above to load announcements</p>
                </div>
              ) : (
                announcements.map(ann => (
                  <div key={ann.id} className="card p-4">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-800 leading-snug">{ann.title}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="badge badge-blue">{ann.course}</span>
                          {ann.posted_at && (
                            <span className="text-xs text-gray-400 flex items-center gap-1">
                              <Clock size={10} />
                              {new Date(ann.posted_at).toLocaleDateString('en-SG', { month: 'short', day: 'numeric' })}
                            </span>
                          )}
                        </div>
                      </div>
                      {!ann.is_read && <span className="badge badge-yellow shrink-0">New</span>}
                    </div>
                    {ann.summary ? (
                      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 mt-2">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <AlertCircle size={11} className="text-nus-blue" />
                          <span className="text-xs font-semibold text-nus-blue">WaveSpeed AI Summary</span>
                        </div>
                        <p className="text-sm text-gray-700 leading-relaxed">{ann.summary}</p>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 italic mt-1">No AI summary available</p>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
