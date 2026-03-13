import { useState, useRef } from 'react'
import axios from 'axios'
import { Upload, Brain, CheckCircle, Calendar, FileImage, Zap } from 'lucide-react'

interface SyllabusEvent {
  id?: number
  event_name: string
  start_time: string | null
  end_time: string | null
  description: string
  event_type: 'exam' | 'deadline' | 'quiz' | 'project' | 'other'
  gcal_synced?: boolean
}

type Step = 'idle' | 'thinking' | 'confirm' | 'syncing' | 'done'

const TYPE_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  exam:     { label: 'Exam',     color: 'text-red-700',    bg: 'bg-red-50 border-red-200' },
  deadline: { label: 'Deadline', color: 'text-blue-700',   bg: 'bg-blue-50 border-blue-200' },
  quiz:     { label: 'Quiz',     color: 'text-yellow-700', bg: 'bg-yellow-50 border-yellow-200' },
  project:  { label: 'Project',  color: 'text-green-700',  bg: 'bg-green-50 border-green-200' },
  other:    { label: 'Event',    color: 'text-gray-700',   bg: 'bg-gray-50 border-gray-200' },
}

const THINKING_STEPS = [
  { icon: '🔍', text: 'Analyzing syllabus image...' },
  { icon: '🤖', text: 'Calling WaveSpeed Vision AI...' },
  { icon: '📋', text: 'Extracting deadlines and exam dates...' },
  { icon: '✅', text: 'Structuring events as JSON...' },
]

function formatDateTime(dt: string | null): string {
  if (!dt) return 'TBD'
  try {
    const d = new Date(dt)
    return d.toLocaleString('en-SG', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return dt
  }
}

export default function SyllabusPage() {
  const [step, setStep] = useState<Step>('idle')
  const [thinkingIndex, setThinkingIndex] = useState(0)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [events, setEvents] = useState<SyllabusEvent[]>([])
  const [dbIds, setDbIds] = useState<number[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [syncResult, setSyncResult] = useState<{ synced_count: number } | null>(null)
  const [gcalCreds, setGcalCreds] = useState('')
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // ── 上传并解析 ──────────────────────────────────────────
  const handleFile = async (file: File) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/heic', 'application/pdf']
    if (!allowed.includes(file.type) && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload an image (JPG, PNG, WEBP) or PDF file')
      return
    }
    setError('')
    setPreviewUrl(URL.createObjectURL(file))
    setStep('thinking')

    // 播放 thinking 动画
    let idx = 0
    const timer = setInterval(() => {
      idx += 1
      setThinkingIndex(idx)
      if (idx >= THINKING_STEPS.length - 1) clearInterval(timer)
    }, 900)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const resp = await axios.post('/api/syllabus/upload', formData)
      clearInterval(timer)
      setThinkingIndex(THINKING_STEPS.length)

      const extracted: SyllabusEvent[] = resp.data.events || []
      const ids: number[] = resp.data.db_ids || []
      setEvents(extracted)
      setDbIds(ids)
      // 默认全选
      setSelectedIds(new Set(ids))
      setStep('confirm')
    } catch (e: any) {
      clearInterval(timer)
      setError(e.response?.data?.detail || 'Failed to extract events. Please try again.')
      setStep('idle')
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  // ── 切换选中 ────────────────────────────────────────────
  const toggleSelect = (id: number | undefined, idx: number) => {
    const key = id ?? idx
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  // ── 同步到 Google Calendar ──────────────────────────────
  const handleSync = async () => {
    if (selectedIds.size === 0) {
      setError('Please select at least one event')
      return
    }
    if (!gcalCreds.trim()) {
      setError('Please paste your Google Calendar credentials JSON')
      return
    }
    let creds: object
    try {
      creds = JSON.parse(gcalCreds)
    } catch {
      setError('Invalid JSON credentials. Please check the format.')
      return
    }

    setError('')
    setStep('syncing')
    try {
      const resp = await axios.post('/api/syllabus/sync-to-calendar', {
        event_ids: Array.from(selectedIds),
        gcal_credentials: creds,
      })
      setSyncResult(resp.data)
      setStep('done')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Sync failed.')
      setStep('confirm')
    }
  }

  // ── Reset ───────────────────────────────────────────────
  const reset = () => {
    setStep('idle')
    setEvents([])
    setDbIds([])
    setSelectedIds(new Set())
    setPreviewUrl(null)
    setSyncResult(null)
    setGcalCreds('')
    setError('')
    setThinkingIndex(0)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-5 py-3 shrink-0">
        <h1 className="font-semibold text-gray-800 text-sm">Syllabus → Calendar</h1>
        <p className="text-xs text-gray-400">OpenClaw syllabus_agent · WaveSpeed Vision AI</p>
      </div>

      <div className="flex-1 scrollable p-5 space-y-4 max-w-3xl mx-auto w-full">

        {/* ── IDLE: 上传区 ── */}
        {step === 'idle' && (
          <div
            onDrop={onDrop}
            onDragOver={e => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-gray-200 rounded-2xl p-12 text-center cursor-pointer hover:border-nus-blue hover:bg-blue-50 transition-colors"
          >
            <Upload size={40} className="text-gray-300 mx-auto mb-4" />
            <div className="text-gray-600 font-medium mb-1">
              Drop your Syllabus photo here
            </div>
            <div className="text-xs text-gray-400 mb-4">
              JPG · PNG · WEBP · HEIC · PDF (multi-page supported)
            </div>
            <div className="btn-primary inline-flex">
              <Upload size={14} />
              Choose Image
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
            />
          </div>
        )}

        {/* ── THINKING: Agent 思考动画 ── */}
        {step === 'thinking' && (
          <div className="card p-6">
            {/* 图片预览 */}
            {previewUrl && (
              <img src={previewUrl} alt="Syllabus" className="w-full max-h-48 object-contain rounded-lg mb-5 bg-gray-50" />
            )}
            <div className="flex items-center gap-2 mb-4">
              <Brain size={20} className="text-nus-blue animate-pulse" />
              <span className="font-medium text-gray-800">Agent is thinking...</span>
            </div>
            <div className="space-y-3">
              {THINKING_STEPS.map((s, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 text-sm transition-all duration-500 ${
                    i <= thinkingIndex ? 'opacity-100' : 'opacity-20'
                  }`}
                >
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
                    i < thinkingIndex
                      ? 'bg-green-100 text-green-600'
                      : i === thinkingIndex
                      ? 'bg-nus-blue text-white animate-pulse'
                      : 'bg-gray-100 text-gray-400'
                  }`}>
                    {i < thinkingIndex ? '✓' : s.icon}
                  </div>
                  <span className={i <= thinkingIndex ? 'text-gray-700' : 'text-gray-400'}>
                    {s.text}
                  </span>
                  {i === thinkingIndex && (
                    <span className="text-xs text-nus-blue animate-pulse">running...</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── CONFIRM: 事件确认卡片 ── */}
        {(step === 'confirm' || step === 'syncing') && events.length > 0 && (
          <>
            {/* 提取成功 banner */}
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-700">
              <CheckCircle size={16} />
              <span>
                Extracted <strong>{events.length} events</strong> from your syllabus via WaveSpeed Vision AI
              </span>
            </div>

            {/* 图片预览（小） */}
            {previewUrl && (
              <img src={previewUrl} alt="Syllabus" className="w-full max-h-32 object-contain rounded-xl bg-gray-50 border border-gray-100" />
            )}

            {/* 事件卡片列表 */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-medium text-gray-700">
                  Confirm Events ({selectedIds.size}/{events.length} selected)
                </h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedIds(new Set(dbIds.length ? dbIds : events.map((_, i) => i)))}
                    className="text-xs text-nus-blue hover:underline"
                  >
                    Select All
                  </button>
                  <span className="text-gray-300">|</span>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    className="text-xs text-gray-400 hover:underline"
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {events.map((ev, idx) => {
                  const key = dbIds[idx] ?? idx
                  const selected = selectedIds.has(key)
                  const style = TYPE_STYLES[ev.event_type] || TYPE_STYLES.other
                  return (
                    <div
                      key={idx}
                      onClick={() => toggleSelect(dbIds[idx], idx)}
                      className={`border rounded-xl p-4 cursor-pointer transition-all ${
                        selected
                          ? 'border-nus-blue bg-blue-50 shadow-sm'
                          : 'border-gray-200 bg-white hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Checkbox */}
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          selected ? 'bg-nus-blue border-nus-blue' : 'border-gray-300'
                        }`}>
                          {selected && <span className="text-white text-xs">✓</span>}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="font-medium text-gray-800 text-sm">{ev.event_name}</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${style.color} ${style.bg}`}>
                              {style.label}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500 flex items-center gap-1">
                            <Calendar size={11} />
                            {formatDateTime(ev.start_time)}
                            {ev.end_time && ev.end_time !== ev.start_time && (
                              <> → {formatDateTime(ev.end_time)}</>
                            )}
                          </div>
                          {ev.description && (
                            <div className="text-xs text-gray-400 mt-1 truncate">{ev.description}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* GCal Credentials */}
            <div className="card p-4">
              <div className="text-sm font-medium text-gray-700 mb-1">Google Calendar Credentials</div>
              <div className="text-xs text-gray-400 mb-2">
                Paste the credentials JSON returned from <code className="bg-gray-100 px-1 rounded">/api/canvas/oauth2callback</code>
              </div>
              <textarea
                value={gcalCreds}
                onChange={e => setGcalCreds(e.target.value)}
                placeholder='{"token": "...", "refresh_token": "...", "client_id": "...", "client_secret": "..."}'
                rows={3}
                className="input text-xs font-mono resize-none"
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            {/* Confirm 按钮 */}
            <button
              onClick={handleSync}
              disabled={step === 'syncing' || selectedIds.size === 0}
              className="btn-primary w-full justify-center py-3 rounded-xl"
            >
              {step === 'syncing' ? (
                <>
                  <Zap size={16} className="animate-spin" />
                  Syncing to Google Calendar...
                </>
              ) : (
                <>
                  <Calendar size={16} />
                  Confirm & Sync {selectedIds.size} Events to Calendar
                </>
              )}
            </button>
          </>
        )}

        {/* ── DONE: 成功 ── */}
        {step === 'done' && syncResult && (
          <div className="text-center py-10">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle size={36} className="text-green-500" />
            </div>
            <div className="text-xl font-semibold text-gray-800 mb-1">
              Successfully Synced!
            </div>
            <div className="text-gray-500 text-sm mb-2">
              <strong>{syncResult.synced_count}</strong> events added to your Google Calendar with reminders
            </div>
            <div className="text-xs text-gray-400 mb-8">
              Powered by OpenClaw syllabus_agent · WaveSpeed Vision AI
            </div>
            <button
              onClick={reset}
              className="btn-primary"
            >
              Upload Another Syllabus
            </button>
          </div>
        )}

        {/* IDLE 时的错误 */}
        {step === 'idle' && error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
