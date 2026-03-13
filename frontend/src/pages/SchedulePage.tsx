import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import {
  Calendar, RefreshCw, Bell, BookOpen, Upload, Mail,
  Download, CheckCircle2, AlertCircle, Clock, FileImage,
  Brain, Zap, ChevronDown, ChevronUp, ExternalLink, Loader2
} from 'lucide-react'

interface ScheduleEvent {
  title: string
  start: string | null
  end: string | null
  description: string
  event_type: string
  source: 'canvas' | 'syllabus'
}

interface Announcement {
  id: number
  course: string
  title: string
  summary: string
  posted_at: string | null
  is_read: boolean
}

const TYPE_STYLES: Record<string, { label: string; badgeClass: string }> = {
  assignment: { label: 'Assignment', badgeClass: 'badge-blue' },
  exam:       { label: 'Exam',       badgeClass: 'badge-red' },
  deadline:   { label: 'Deadline',   badgeClass: 'badge-yellow' },
  quiz:       { label: 'Quiz',       badgeClass: 'badge-yellow' },
  project:    { label: 'Project',    badgeClass: 'badge-green' },
  other:      { label: 'Event',      badgeClass: 'badge-gray' },
}

const THINKING_STEPS = [
  { icon: '🔍', text: 'Analyzing syllabus image...' },
  { icon: '🤖', text: 'Calling WaveSpeed Vision AI...' },
  { icon: '📋', text: 'Extracting deadlines & exam dates...' },
  { icon: '✅', text: 'Structuring events...' },
]

function DaysChip({ start }: { start: string | null }) {
  if (!start) return <span className="badge badge-gray">No date</span>
  const days = Math.ceil((new Date(start).getTime() - Date.now()) / 86400000)
  if (days < 0) return <span className="badge badge-gray">Past</span>
  if (days === 0) return <span className="badge badge-red">Today</span>
  if (days <= 3) return <span className="badge badge-red">{days}d left</span>
  if (days <= 7) return <span className="badge badge-yellow">{days}d left</span>
  return <span className="badge badge-gray">{days}d left</span>
}

export default function SchedulePage() {
  // Canvas
  const [canvasToken, setCanvasToken] = useState('')
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<any>(null)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [showAnnouncements, setShowAnnouncements] = useState(false)

  // Syllabus
  const [syllabusStep, setSyllabusStep] = useState<'idle' | 'thinking' | 'done'>('idle')
  const [thinkingIndex, setThinkingIndex] = useState(0)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [syllabusCount, setSyllabusCount] = useState(0)
  const [syllabusError, setSyllabusError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // Unified events
  const [events, setEvents] = useState<ScheduleEvent[]>([])
  const [emailAddr, setEmailAddr] = useState('')
  const [isSendingEmail, setIsSendingEmail] = useState(false)
  const [emailResult, setEmailResult] = useState<string | null>(null)

  // Google Calendar
  const [gcalAuthorized, setGcalAuthorized] = useState(false)
  const [gcalPushing, setGcalPushing] = useState(false)
  const [gcalResult, setGcalResult] = useState<string | null>(null)

  const fetchEvents = async () => {
    try {
      const r = await axios.get('/api/schedule/events')
      setEvents(r.data)
    } catch {}
  }

  const fetchAnnouncements = async () => {
    try {
      const r = await axios.get('/api/canvas/announcements')
      setAnnouncements(r.data)
    } catch {}
  }

  const checkGcalStatus = async () => {
    try {
      const r = await axios.get('/api/schedule/gcal/status')
      setGcalAuthorized(r.data.authorized)
    } catch {}
  }

  // 启动时从本地加载已保存的偏好
  useEffect(() => {
    fetchEvents()
    fetchAnnouncements()
    checkGcalStatus()
    axios.get('/api/prefs').then(r => {
      if (r.data.canvas_token) setCanvasToken(r.data.canvas_token)
      if (r.data.email) setEmailAddr(r.data.email)
    }).catch(() => {})

    // Listen for OAuth callback message from popup window
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === 'gcal_authorized') {
        setGcalAuthorized(true)
        setGcalResult('✅ Google Calendar connected!')
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  // ── Canvas Sync ─────────────────────────────────────────
  const handleCanvasSync = async () => {
    if (!canvasToken.trim()) { alert('Please enter your Canvas access token'); return }
    setIsSyncing(true); setSyncResult(null)
    try {
      const r = await axios.post('/api/schedule/sync-canvas', { canvas_token: canvasToken })
      setSyncResult(r.data)
      await fetchEvents()
      await fetchAnnouncements()
      // 保存 token 到本地，下次自动填入
      axios.post('/api/prefs', { canvas_token: canvasToken }).catch(() => {})
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Canvas sync failed')
    } finally {
      setIsSyncing(false)
    }
  }

  // ── Syllabus Upload ──────────────────────────────────────
  const handleSyllabusFile = async (file: File) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf']
    if (!allowed.includes(file.type) && !file.name.toLowerCase().endsWith('.pdf')) {
      setSyllabusError('Please upload an image (JPG/PNG/WEBP) or PDF')
      return
    }
    setSyllabusError('')
    setPreviewUrl(file.type.startsWith('image/') ? URL.createObjectURL(file) : null)
    setSyllabusStep('thinking')
    setThinkingIndex(0)

    const timer = setInterval(() => {
      setThinkingIndex(i => { if (i >= THINKING_STEPS.length - 1) { clearInterval(timer); return i } return i + 1 })
    }, 900)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const r = await axios.post('/api/schedule/upload-syllabus', formData)
      clearInterval(timer)
      setThinkingIndex(THINKING_STEPS.length)
      setSyllabusCount((r.data.events || []).length)
      setSyllabusStep('done')
      await fetchEvents()
    } catch (e: any) {
      clearInterval(timer)
      setSyllabusError(e.response?.data?.detail || 'Failed to extract events')
      setSyllabusStep('idle')
    }
  }

  // ── Google Calendar ──────────────────────────────────────
  const handleGcalConnect = async () => {
    try {
      const r = await axios.get('/api/schedule/gcal/auth-url')
      const popup = window.open(r.data.url, 'gcal_auth', 'width=500,height=650,left=400,top=100')
      // Fallback: poll if popup was blocked
      if (!popup) window.location.href = r.data.url
    } catch (e: any) {
      alert('Failed to get auth URL: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleGcalPush = async () => {
    setGcalPushing(true); setGcalResult(null)
    try {
      const r = await axios.post('/api/schedule/gcal/push')
      setGcalResult(`✅ Agent pushed ${r.data.pushed}/${r.data.total} events to Google Calendar!`)
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message
      if (e.response?.status === 401) {
        setGcalResult('❌ Not authorized. Please connect Google Calendar first.')
        setGcalAuthorized(false)
      } else {
        setGcalResult(`❌ Push failed: ${msg}`)
      }
    } finally {
      setGcalPushing(false)
    }
  }

  const handleGcalDisconnect = async () => {
    await axios.post('/api/schedule/gcal/disconnect').catch(() => {})
    setGcalAuthorized(false)
    setGcalResult(null)
  }

  // ── Download ICS ─────────────────────────────────────────
  const handleDownloadIcs = async () => {
    try {
      const r = await axios.get('/api/schedule/download-ics', { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([r.data], { type: 'text/calendar' }))
      const a = document.createElement('a'); a.href = url; a.download = 'nus_schedule.ics'; a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      alert(e.response?.data?.detail || 'No events to export yet')
    }
  }

  // ── Send Email ───────────────────────────────────────────
  const handleSendEmail = async () => {
    if (!emailAddr.trim()) { alert('Please enter your email address'); return }
    setIsSendingEmail(true); setEmailResult(null)
    try {
      await axios.post('/api/schedule/send-email', { to_email: emailAddr })
      setEmailResult(`✅ Sent ${events.length} events to ${emailAddr}`)
      axios.post('/api/prefs', { email: emailAddr }).catch(() => {})
    } catch (e: any) {
      setEmailResult(`✗ ${e.response?.data?.detail || 'Email failed'}`)
    } finally {
      setIsSendingEmail(false)
    }
  }

  const canvasEvents = events.filter(e => e.source === 'canvas')
  const syllabusEvents = events.filter(e => e.source === 'syllabus')
  const urgentCount = events.filter(e => {
    if (!e.start) return false
    const d = Math.ceil((new Date(e.start).getTime() - Date.now()) / 86400000)
    return d >= 0 && d <= 3
  }).length

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 shrink-0">
        <h1 className="font-semibold text-gray-800 text-sm">Schedule Agent</h1>
        <p className="text-xs text-gray-400">Canvas Sync + Syllabus Vision · Local Calendar Export · Email Reminder</p>
      </div>

      <div className="flex-1 scrollable px-5 py-4 space-y-4">

        {/* Stats */}
        {events.length > 0 && (
          <div className="grid grid-cols-4 gap-3">
            <div className="card p-3 text-center">
              <div className="text-2xl font-bold text-nus-blue">{events.length}</div>
              <div className="text-xs text-gray-400 mt-0.5">Total Events</div>
            </div>
            <div className="card p-3 text-center">
              <div className="text-2xl font-bold text-blue-500">{canvasEvents.length}</div>
              <div className="text-xs text-gray-400 mt-0.5">From Canvas</div>
            </div>
            <div className="card p-3 text-center">
              <div className="text-2xl font-bold text-purple-500">{syllabusEvents.length}</div>
              <div className="text-xs text-gray-400 mt-0.5">From Syllabus</div>
            </div>
            <div className="card p-3 text-center">
              <div className={`text-2xl font-bold ${urgentCount > 0 ? 'text-red-500' : 'text-gray-300'}`}>{urgentCount}</div>
              <div className="text-xs text-gray-400 mt-0.5">Due Soon</div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          {/* ── Canvas Sync ── */}
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-2">
              <BookOpen size={14} className="text-nus-blue" /> Canvas Sync
            </h2>
            <p className="text-xs text-gray-400 mb-3">Canvas → Account → Settings → New Access Token</p>
            <div className="flex gap-2 mb-3">
              <input
                type="password"
                value={canvasToken}
                onChange={e => setCanvasToken(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCanvasSync()}
                placeholder="Canvas access token..."
                className="input text-sm flex-1"
              />
              <button onClick={handleCanvasSync} disabled={isSyncing} className="btn-primary shrink-0">
                <RefreshCw size={13} className={isSyncing ? 'animate-spin' : ''} />
                {isSyncing ? 'Syncing…' : 'Sync'}
              </button>
            </div>
            {syncResult && (
              <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-100 rounded-lg text-xs text-green-700">
                <CheckCircle2 size={13} />
                {syncResult.courses_synced} courses · {syncResult.assignments_synced} assignments · {syncResult.announcements_synced} announcements
              </div>
            )}

            {/* Announcements collapsible */}
            {announcements.length > 0 && (
              <div className="mt-3">
                <button
                  onClick={() => setShowAnnouncements(v => !v)}
                  className="flex items-center gap-1.5 text-xs text-nus-blue hover:underline"
                >
                  <Bell size={12} /> {announcements.length} announcements
                  {showAnnouncements ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {showAnnouncements && (
                  <div className="mt-2 space-y-2 max-h-48 overflow-y-auto scrollable">
                    {announcements.map(ann => (
                      <div key={ann.id} className="p-2.5 bg-blue-50 border border-blue-100 rounded-lg">
                        <div className="text-xs font-semibold text-gray-700 truncate">{ann.title}</div>
                        <div className="text-xs text-gray-400 mt-0.5">{ann.course}</div>
                        {ann.summary && (
                          <div className="text-xs text-gray-600 mt-1 leading-relaxed">{ann.summary}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Syllabus Upload ── */}
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-2">
              <FileImage size={14} className="text-nus-blue" /> Syllabus → Events
            </h2>
            <p className="text-xs text-gray-400 mb-3">WaveSpeed Vision AI extracts dates from photos or PDFs</p>

            {syllabusStep === 'idle' && (
              <label
                className="flex flex-col items-center justify-center border-2 border-dashed border-gray-200 rounded-xl p-5 cursor-pointer hover:border-nus-blue hover:bg-blue-50 transition-all"
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleSyllabusFile(f) }}
              >
                <Upload size={22} className="text-gray-300 mb-1.5" />
                <span className="text-xs font-medium text-gray-500">Drop image or PDF here</span>
                <span className="text-xs text-gray-400">JPG · PNG · PDF</span>
                <input ref={fileRef} type="file" accept="image/*,.pdf" className="hidden"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleSyllabusFile(f) }} />
              </label>
            )}

            {syllabusStep === 'thinking' && (
              <div className="space-y-2 p-3 bg-gray-50 rounded-xl">
                {previewUrl && <img src={previewUrl} className="w-full max-h-24 object-contain rounded-lg bg-white mb-2" />}
                <div className="flex items-center gap-2 mb-2">
                  <Brain size={14} className="text-nus-blue animate-pulse" />
                  <span className="text-xs font-medium text-gray-700">Agent thinking…</span>
                </div>
                {THINKING_STEPS.map((s, i) => (
                  <div key={i} className={`flex items-center gap-2 text-xs transition-all ${i <= thinkingIndex ? 'opacity-100' : 'opacity-20'}`}>
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs shrink-0 ${i < thinkingIndex ? 'bg-green-100 text-green-600' : i === thinkingIndex ? 'bg-nus-blue text-white animate-pulse' : 'bg-gray-100 text-gray-400'}`}>
                      {i < thinkingIndex ? '✓' : s.icon}
                    </span>
                    <span className={i <= thinkingIndex ? 'text-gray-700' : 'text-gray-300'}>{s.text}</span>
                  </div>
                ))}
              </div>
            )}

            {syllabusStep === 'done' && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-100 rounded-lg text-xs text-green-700">
                  <CheckCircle2 size={13} />
                  Extracted <strong>{syllabusCount} events</strong> via WaveSpeed Vision AI
                </div>
                <button onClick={() => { setSyllabusStep('idle'); setSyllabusCount(0); setPreviewUrl(null) }}
                  className="btn-secondary text-xs w-full justify-center">
                  Upload Another
                </button>
              </div>
            )}

            {syllabusError && (
              <div className="flex items-center gap-2 p-2.5 bg-red-50 border border-red-100 rounded-lg text-xs text-red-600 mt-2">
                <AlertCircle size={13} /> {syllabusError}
              </div>
            )}
          </div>
        </div>

        {/* ── Export & Sync ── */}
        {events.length > 0 && (
          <div className="card p-4 space-y-4">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Calendar size={14} className="text-nus-blue" /> Sync to Calendar
            </h2>

            {/* Option 1: Google Calendar Agent Auto-Push ★ */}
            <div className="rounded-xl border-2 border-nus-blue/30 bg-blue-50/40 p-3.5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-nus-blue flex items-center gap-1.5 mb-0.5">
                    <span className="text-base">📅</span> Agent Auto-Push to Google Calendar
                    <span className="text-[10px] bg-nus-blue text-white px-1.5 py-0.5 rounded-full ml-1">Recommended</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    One-click authorization → Agent automatically creates all {events.length} events with reminders in your Google Calendar
                  </div>
                </div>
                <div className="shrink-0 flex flex-col items-end gap-2">
                  {!gcalAuthorized ? (
                    <button onClick={handleGcalConnect} className="btn-primary text-xs whitespace-nowrap">
                      <ExternalLink size={12} /> Connect Google Calendar
                    </button>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <CheckCircle2 size={12} /> Connected
                      </span>
                      <button onClick={handleGcalPush} disabled={gcalPushing} className="btn-primary text-xs whitespace-nowrap">
                        {gcalPushing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
                        {gcalPushing ? 'Pushing…' : `Push ${events.length} Events`}
                      </button>
                      <button onClick={handleGcalDisconnect} className="text-xs text-gray-400 hover:text-red-500 underline">
                        Disconnect
                      </button>
                    </div>
                  )}
                </div>
              </div>
              {gcalResult && (
                <div className={`text-xs mt-2.5 px-2 py-1.5 rounded-lg ${gcalResult.startsWith('✅') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                  {gcalResult}
                </div>
              )}
            </div>

            <div className="flex gap-3 items-start">
              {/* Option 2: Download ICS */}
              <div className="flex-1">
                <div className="text-xs text-gray-500 mb-2">
                  <strong>Option 2:</strong> Download .ics → double-click to import into any calendar app
                </div>
                <button onClick={handleDownloadIcs} className="btn-secondary text-xs">
                  <Download size={13} /> Download .ics ({events.length} events)
                </button>
              </div>

              <div className="w-px self-stretch bg-gray-100" />

              {/* Option 3: Email */}
              <div className="flex-1">
                <div className="text-xs text-gray-500 mb-2">
                  <strong>Option 3:</strong> Email .ics + schedule summary (with reminders)
                </div>
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={emailAddr}
                    onChange={e => setEmailAddr(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSendEmail()}
                    placeholder="your@email.com"
                    className="input text-sm flex-1"
                  />
                  <button onClick={handleSendEmail} disabled={isSendingEmail} className="btn-secondary text-xs shrink-0">
                    <Mail size={12} className={isSendingEmail ? 'animate-pulse' : ''} />
                    {isSendingEmail ? 'Sending…' : 'Send'}
                  </button>
                </div>
                {emailResult && (
                  <div className={`text-xs mt-1.5 ${emailResult.startsWith('✅') ? 'text-green-600' : 'text-red-500'}`}>
                    {emailResult}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Events Timeline ── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">All Events Timeline</h2>
            <div className="flex gap-1.5">
              <span className="badge badge-blue">Canvas {canvasEvents.length}</span>
              <span className="badge badge-gray">Syllabus {syllabusEvents.length}</span>
            </div>
          </div>

          {events.length === 0 ? (
            <div className="card p-12 text-center">
              <Calendar size={32} className="text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">No events yet</p>
              <p className="text-xs text-gray-300 mt-1">Sync Canvas or upload a syllabus to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {[...events]
                .sort((a, b) => (a.start ?? '9999') < (b.start ?? '9999') ? -1 : 1)
                .map((ev, i) => {
                  const s = TYPE_STYLES[ev.event_type] || TYPE_STYLES.other
                  const days = ev.start ? Math.ceil((new Date(ev.start).getTime() - Date.now()) / 86400000) : null
                  const urgent = days !== null && days >= 0 && days <= 3
                  return (
                    <div key={i} className={`card p-3.5 flex items-center gap-3 ${urgent ? 'border-red-200 bg-red-50/40' : ''}`}>
                      <div className={`w-1 self-stretch rounded-full shrink-0 ${
                        days === null ? 'bg-gray-200' : days < 0 ? 'bg-gray-200' :
                        days <= 1 ? 'bg-red-400' : days <= 3 ? 'bg-yellow-400' : days <= 7 ? 'bg-blue-400' : 'bg-green-400'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{ev.title}</div>
                        {ev.description && <div className="text-xs text-gray-400 truncate mt-0.5">{ev.description}</div>}
                      </div>
                      <div className="text-right shrink-0 space-y-1">
                        <div className="text-xs text-gray-600 font-medium">
                          {ev.start ? new Date(ev.start).toLocaleDateString('en-SG', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                        </div>
                        <div className="flex items-center justify-end gap-1.5">
                          <span className={`badge ${s.badgeClass}`}>{s.label}</span>
                          <DaysChip start={ev.start} />
                          <span className={`badge ${ev.source === 'canvas' ? 'badge-blue' : 'badge-gray'}`}>
                            {ev.source === 'canvas' ? 'Canvas' : 'Syllabus'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
