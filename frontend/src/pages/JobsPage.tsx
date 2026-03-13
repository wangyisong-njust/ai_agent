import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import {
  Briefcase, Upload, Zap, CheckCircle2, XCircle, Clock,
  RotateCcw, FileText, Search, Bot, ChevronRight, Eye, EyeOff
} from 'lucide-react'

interface ApplicationRecord {
  id: number
  platform: string
  company: string
  role: string
  job_url: string
  status: string
  match_score: number
  applied_at: string
}

interface AgentLog {
  type: string
  message?: string
  title?: string
  company?: string
  score?: number
  recommendation?: string
  status?: string
  reason?: string
  step?: number
  count?: number
  jobs?: { title: string; company: string; url: string }[]
  applied?: number
  failed?: number
  results?: { title: string; company: string; score: number; status: string }[]
}

type Mode = 'idle' | 'running' | 'done'

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 75 ? 'badge-green' : score >= 55 ? 'badge-yellow' : 'badge-red'
  return <span className={`badge ${cls} font-bold`}>{score}/100</span>
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'applied') return <CheckCircle2 size={14} className="text-green-500" />
  if (status === 'failed') return <XCircle size={14} className="text-red-400" />
  return <Clock size={14} className="text-yellow-500" />
}

export default function JobsPage() {
  // Resume
  const [resumeData, setResumeData] = useState<any>(null)
  const [resumePath, setResumePath] = useState('')
  const [dragOver, setDragOver] = useState(false)

  // Search config
  const [keywords, setKeywords] = useState('')
  const [location, setLocation] = useState('Singapore')
  const [maxApply, setMaxApply] = useState(5)
  const [minScore, setMinScore] = useState(65)
  const [loginMode, setLoginMode] = useState<'cookie' | 'password'>('cookie')
  const [linkedinEmail, setLinkedinEmail] = useState('')
  const [linkedinPassword, setLinkedinPassword] = useState('')
  const [linkedinCookie, setLinkedinCookie] = useState('')
  const [showPass, setShowPass] = useState(false)

  // Agent state
  const [mode, setMode] = useState<Mode>('idle')
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [foundJobs, setFoundJobs] = useState<{ title: string; company: string; url: string }[]>([])
  const [summary, setSummary] = useState<{ applied: number; failed: number; results: any[] } | null>(null)
  const [currentStep, setCurrentStep] = useState(0)

  // History
  const [history, setHistory] = useState<ApplicationRecord[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    axios.get('/api/jobs/history').then(r => setHistory(r.data)).catch(() => {})
    // 加载已保存的偏好
    axios.get('/api/prefs').then(r => {
      if (r.data.linkedin_cookie) setLinkedinCookie(r.data.linkedin_cookie)
      if (r.data.linkedin_email) setLinkedinEmail(r.data.linkedin_email)
      if (r.data.keywords) setKeywords(r.data.keywords)
      if (r.data.location) setLocation(r.data.location)
      // 如果有 cookie 则自动切换到 cookie 模式
      if (r.data.linkedin_cookie_saved) setLoginMode('cookie')
    }).catch(() => {})
  }, [])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const handleResumeFile = async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const resp = await axios.post('/api/jobs/upload-resume', formData)
      setResumeData(resp.data.resume)
      setResumePath(resp.data.resume.file_path || '')
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Upload failed')
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleResumeFile(file)
  }

  const startAgent = async () => {
    if (!resumePath) { alert('Please upload your resume first'); return }
    if (!keywords.trim()) { alert('Please enter job keywords'); return }
    if (loginMode === 'cookie' && !linkedinCookie.trim()) { alert('Please enter your LinkedIn li_at cookie'); return }
    if (loginMode === 'password' && (!linkedinEmail || !linkedinPassword)) { alert('Please enter LinkedIn credentials'); return }

    setMode('running')
    setLogs([])
    setFoundJobs([])
    setSummary(null)
    setCurrentStep(0)
    // 保存偏好到本地
    axios.post('/api/prefs', {
      linkedin_cookie: loginMode === 'cookie' ? linkedinCookie : undefined,
      linkedin_email: loginMode === 'password' ? linkedinEmail : undefined,
      keywords,
      location,
    }).catch(() => {})

    try {
      const response = await fetch('/api/jobs/auto-apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_path: resumePath,
          resume_data: resumeData,
          keywords,
          location,
          max_apply: maxApply,
          min_score: minScore,
          linkedin_email: loginMode === 'password' ? linkedinEmail : '',
          linkedin_password: loginMode === 'password' ? linkedinPassword : '',
          linkedin_cookie: loginMode === 'cookie' ? linkedinCookie : '',
        }),
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event: AgentLog = JSON.parse(line.slice(6))
            setLogs(prev => [...prev, event])

            if (event.type === 'step' && event.step) setCurrentStep(event.step)
            if (event.type === 'jobs_found' && event.jobs) setFoundJobs(event.jobs)
            if (event.type === 'done') {
              setSummary({ applied: event.applied || 0, failed: event.failed || 0, results: event.results || [] })
              setMode('done')
              axios.get('/api/jobs/history').then(r => setHistory(r.data)).catch(() => {})
            }
            if (event.type === 'error') { setMode('done'); setLogs(prev => [...prev, event]) }
          } catch {}
        }
      }
    } catch (err) {
      setLogs(prev => [...prev, { type: 'error', message: 'Connection failed. Make sure backend is running.' }])
      setMode('done')
    }
  }

  const reset = () => {
    setMode('idle'); setLogs([]); setFoundJobs([]); setSummary(null); setCurrentStep(0)
  }

  const STEPS = ['Search Jobs', 'AI Screening', 'Auto Apply']

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 shrink-0 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-gray-800 text-sm">Job Application Agent</h1>
          <p className="text-xs text-gray-400">OpenClaw job_agent · LinkedIn Auto Search & Apply</p>
        </div>
        {mode !== 'idle' && (
          <button onClick={reset} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
            <RotateCcw size={12} /> Reset
          </button>
        )}
      </div>

      <div className="flex-1 scrollable">
        <div className="p-5 grid grid-cols-5 gap-5">

          {/* ── Left: Config + Agent Console ── */}
          <div className="col-span-3 space-y-4">

            {/* Step progress */}
            {mode !== 'idle' && (
              <div className="card p-4">
                <div className="flex items-center gap-0">
                  {STEPS.map((s, i) => (
                    <div key={i} className="flex items-center flex-1 last:flex-none">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 transition-all ${
                        currentStep > i + 1 ? 'bg-green-500 text-white' :
                        currentStep === i + 1 ? 'bg-nus-blue text-white animate-pulse' :
                        'bg-gray-100 text-gray-400'
                      }`}>
                        {currentStep > i + 1 ? <CheckCircle2 size={14} /> : i + 1}
                      </div>
                      <div className="ml-2 mr-3">
                        <div className={`text-xs font-medium ${
                          currentStep === i + 1 ? 'text-nus-blue' :
                          currentStep > i + 1 ? 'text-green-600' : 'text-gray-400'
                        }`}>{s}</div>
                      </div>
                      {i < STEPS.length - 1 && (
                        <div className={`h-px flex-1 mr-3 transition-colors ${currentStep > i + 1 ? 'bg-green-400' : 'bg-gray-200'}`} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Config panel (hide when running) */}
            {mode === 'idle' && (
              <>
                {/* Resume Upload */}
                <div className="card p-4">
                  <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <FileText size={14} className="text-nus-blue" /> Step 1 · Upload Resume
                  </h2>
                  {resumeData ? (
                    <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                      <CheckCircle2 size={16} className="text-green-500 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-green-800">{resumeData.name || 'Resume uploaded'}</div>
                        <div className="text-xs text-green-600 truncate">{resumeData.email} · {resumeData.skills?.slice(0, 3).join(', ')}</div>
                      </div>
                      <button onClick={() => { setResumeData(null); setResumePath('') }} className="text-xs text-gray-400 hover:text-red-500 ml-auto">
                        <RotateCcw size={12} />
                      </button>
                    </div>
                  ) : (
                    <label
                      className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-8 cursor-pointer transition-all ${
                        dragOver ? 'border-nus-blue bg-blue-50' : 'border-gray-200 hover:border-nus-blue hover:bg-gray-50'
                      }`}
                      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                      onDragLeave={() => setDragOver(false)}
                      onDrop={handleDrop}
                    >
                      <Upload size={28} className={`mb-2 ${dragOver ? 'text-nus-blue' : 'text-gray-300'}`} />
                      <span className="text-sm font-medium text-gray-500">Drop PDF resume here or click to browse</span>
                      <span className="text-xs text-gray-400 mt-1">WaveSpeed AI will parse your resume</span>
                      <input type="file" accept=".pdf" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleResumeFile(f) }} />
                    </label>
                  )}
                </div>

                {/* Search config */}
                <div className="card p-4">
                  <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <Search size={14} className="text-nus-blue" /> Step 2 · Job Search Settings
                  </h2>
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Job Keywords</label>
                      <input className="input text-sm" placeholder="e.g. Software Engineer Intern, Data Analyst..." value={keywords} onChange={e => setKeywords(e.target.value)} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">Location</label>
                        <input className="input text-sm" value={location} onChange={e => setLocation(e.target.value)} />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">Max Applications</label>
                        <select className="input text-sm" value={maxApply} onChange={e => setMaxApply(Number(e.target.value))}>
                          {[3, 5, 10, 15, 20].map(n => <option key={n} value={n}>{n} jobs</option>)}
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Minimum Match Score: <strong className="text-nus-blue">{minScore}/100</strong></label>
                      <input type="range" min={40} max={90} step={5} value={minScore} onChange={e => setMinScore(Number(e.target.value))} className="w-full accent-nus-blue" />
                      <div className="flex justify-between text-xs text-gray-300 mt-0.5"><span>40 (Loose)</span><span>90 (Strict)</span></div>
                    </div>
                  </div>
                </div>

                {/* LinkedIn credentials */}
                <div className="card p-4">
                  <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <Briefcase size={14} className="text-nus-blue" /> Step 3 · LinkedIn Account
                  </h2>

                  {/* Mode toggle */}
                  <div className="flex gap-1 p-1 bg-gray-100 rounded-lg mb-3 w-fit">
                    <button onClick={() => setLoginMode('cookie')}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${loginMode === 'cookie' ? 'bg-white shadow-sm text-nus-blue' : 'text-gray-500'}`}>
                      Cookie (Google Login)
                    </button>
                    <button onClick={() => setLoginMode('password')}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${loginMode === 'password' ? 'bg-white shadow-sm text-nus-blue' : 'text-gray-500'}`}>
                      Email & Password
                    </button>
                  </div>

                  {loginMode === 'cookie' ? (
                    <div className="space-y-2">
                      <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700 space-y-1">
                        <div className="font-semibold">How to get your li_at cookie:</div>
                        <ol className="list-decimal list-inside space-y-0.5 text-blue-600">
                          <li>Open LinkedIn in Chrome, make sure you're logged in</li>
                          <li>Press <kbd className="bg-blue-100 px-1 rounded">F12</kbd> → Application → Cookies → linkedin.com</li>
                          <li>Find the cookie named <strong>li_at</strong>, copy its Value</li>
                        </ol>
                      </div>
                      <input
                        className="input text-sm font-mono"
                        placeholder="Paste li_at cookie value here..."
                        value={linkedinCookie}
                        onChange={e => setLinkedinCookie(e.target.value)}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs text-gray-400">Used only for Easy Apply. Not stored after session ends.</p>
                      <input className="input text-sm" type="email" placeholder="LinkedIn email" value={linkedinEmail} onChange={e => setLinkedinEmail(e.target.value)} />
                      <div className="relative">
                        <input className="input text-sm pr-10" type={showPass ? 'text' : 'password'} placeholder="LinkedIn password" value={linkedinPassword} onChange={e => setLinkedinPassword(e.target.value)} />
                        <button type="button" onClick={() => setShowPass(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                          {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Launch button */}
                <button onClick={startAgent} className="btn-primary w-full justify-center py-3 text-base rounded-xl">
                  <Bot size={18} />
                  Launch Job Agent
                </button>
              </>
            )}

            {/* Agent Console */}
            {mode !== 'idle' && (
              <div className="card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Bot size={14} className="text-nus-blue" />
                  <h2 className="text-sm font-semibold text-gray-700">Agent Console</h2>
                  {mode === 'running' && <span className="badge badge-blue animate-pulse">Running</span>}
                  {mode === 'done' && <span className="badge badge-green">Done</span>}
                </div>
                <div className="space-y-1.5 max-h-80 overflow-y-auto scrollable pr-1 font-mono text-xs">
                  {logs.map((log, i) => {
                    if (log.type === 'step') return (
                      <div key={i} className="text-nus-blue font-semibold py-0.5">{log.message}</div>
                    )
                    if (log.type === 'analyzing') return (
                      <div key={i} className="text-gray-500 flex gap-2">
                        <span className="text-gray-300">[{log.index}/{log.total}]</span>
                        <span>Analyzing: {log.title} @ {log.company}...</span>
                      </div>
                    )
                    if (log.type === 'analyzed') return (
                      <div key={i} className={`flex gap-2 ${log.recommendation === 'apply' ? 'text-green-600' : 'text-gray-400'}`}>
                        <span>{log.recommendation === 'apply' ? '✓' : '✗'}</span>
                        <span>{log.title} @ {log.company}</span>
                        <span className="ml-auto">{log.score}/100</span>
                      </div>
                    )
                    if (log.type === 'applying') return (
                      <div key={i} className="text-yellow-600 flex gap-2">
                        <span>→</span><span>Applying: {log.title} @ {log.company} ({log.score}/100)</span>
                      </div>
                    )
                    if (log.type === 'applied') return (
                      <div key={i} className="text-green-600 flex gap-2">
                        <span>✓</span><span>Applied: {log.title} @ {log.company}</span>
                      </div>
                    )
                    if (log.type === 'skipped') return (
                      <div key={i} className="text-gray-400 flex gap-2">
                        <span>–</span><span>Skipped: {log.title} ({log.reason})</span>
                      </div>
                    )
                    if (log.type === 'error') return (
                      <div key={i} className="text-red-500">✗ {log.message}</div>
                    )
                    if (log.type === 'warn') return (
                      <div key={i} className="text-yellow-500">⚠ {log.message}</div>
                    )
                    if (log.type === 'done') return (
                      <div key={i} className="text-green-600 font-semibold border-t border-gray-100 pt-2 mt-1">{log.message}</div>
                    )
                    return null
                  })}
                  <div ref={logsEndRef} />
                </div>
              </div>
            )}

            {/* Summary */}
            {summary && mode === 'done' && (
              <div className="card p-4">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">Session Results</h2>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="text-center p-3 bg-green-50 rounded-xl">
                    <div className="text-2xl font-bold text-green-600">{summary.applied}</div>
                    <div className="text-xs text-gray-500">Successfully Applied</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-xl">
                    <div className="text-2xl font-bold text-gray-400">{summary.failed}</div>
                    <div className="text-xs text-gray-500">Skipped / Failed</div>
                  </div>
                </div>
                <div className="space-y-2">
                  {summary.results.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <StatusIcon status={r.status} />
                      <span className="flex-1 text-gray-700 truncate">{r.title} @ {r.company}</span>
                      <ScoreBadge score={r.score} />
                    </div>
                  ))}
                </div>
                <button onClick={reset} className="btn-secondary w-full justify-center mt-3">
                  <RotateCcw size={13} /> Start New Search
                </button>
              </div>
            )}

            {/* Jobs found list */}
            {foundJobs.length > 0 && (
              <div className="card p-4">
                <h2 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <Search size={13} className="text-nus-blue" /> Jobs Found ({foundJobs.length})
                </h2>
                <div className="space-y-1.5 max-h-48 overflow-y-auto scrollable">
                  {foundJobs.map((j, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-gray-600">
                      <ChevronRight size={11} className="text-gray-300 shrink-0" />
                      <span className="font-medium truncate">{j.title}</span>
                      <span className="text-gray-400">@ {j.company}</span>
                      <a href={j.url} target="_blank" rel="noreferrer" className="ml-auto text-nus-blue hover:underline shrink-0">View</a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── Right: History ── */}
          <div className="col-span-2">
            <div className="card p-4 h-full flex flex-col">
              <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Clock size={14} className="text-nus-blue" /> Application History
              </h2>
              <div className="flex-1 overflow-y-auto space-y-2 scrollable pr-1">
                {history.length === 0 ? (
                  <div className="text-center py-12">
                    <Briefcase size={28} className="text-gray-200 mx-auto mb-2" />
                    <p className="text-sm text-gray-400">No applications yet</p>
                    <p className="text-xs text-gray-300 mt-1">Launch the agent to start applying</p>
                  </div>
                ) : (
                  history.map(r => (
                    <div key={r.id} className="p-3 border border-gray-100 rounded-xl hover:border-gray-200 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">{r.role}</div>
                          <div className="text-xs text-gray-500">{r.company}</div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <StatusIcon status={r.status} />
                          <span className="text-xs text-gray-500 capitalize">{r.status}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <span className={`badge ${r.match_score >= 75 ? 'badge-green' : r.match_score >= 55 ? 'badge-yellow' : 'badge-red'}`}>
                          {r.match_score}% match
                        </span>
                        <span className="badge badge-gray">{r.platform}</span>
                        {r.applied_at && (
                          <span className="text-xs text-gray-400">
                            {new Date(r.applied_at).toLocaleDateString('en-SG', { month: 'short', day: 'numeric' })}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
