import { useState, useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin, Clock, Navigation, CheckCircle, BookOpen, Loader2, Send, ChevronRight } from 'lucide-react'

// Fix Leaflet default marker icon broken by bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// ── Types ──────────────────────────────────────────────────────────────────
interface Location {
  key: string
  name: string
  lat: number
  lng: number
  type: string
}

interface TimelineCard {
  id: string
  type: 'depart' | 'transit' | 'service' | 'class' | 'arrive'
  time: string
  end_time?: string
  title: string
  location: string
  location_key?: string | null
  description: string
  duration_min: number
  lat: number
  lng: number
  conflict: boolean
  hours?: string
}

interface RouteResult {
  narrative: string
  timeline: TimelineCard[]
  route: {
    locations: Location[]
    segments: any[]
    total_min: number
  }
  skills_used: string[]
}

// ── Map Component ─────────────────────────────────────────────────────────
const TYPE_COLORS: Record<string, string> = {
  origin: '#3b82f6',
  checkin_office: '#f59e0b',
  destination: '#10b981',
  stop: '#8b5cf6',
}

function LeafletMap({ locations, activeIdx }: { locations: Location[]; activeIdx: number }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersRef = useRef<L.Marker[]>([])
  const polylineRef = useRef<L.Polyline | null>(null)

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = L.map(containerRef.current, { zoomControl: true }).setView([1.299, 103.776], 14)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Update markers & polyline
  useEffect(() => {
    const map = mapRef.current
    if (!map || locations.length === 0) return

    // Clear old layers
    markersRef.current.forEach(m => map.removeLayer(m))
    markersRef.current = []
    if (polylineRef.current) {
      map.removeLayer(polylineRef.current)
      polylineRef.current = null
    }

    const latlngs: L.LatLngExpression[] = []

    locations.forEach((loc, idx) => {
      const color = TYPE_COLORS[loc.type] || '#6b7280'
      const isActive = idx === activeIdx
      const size = isActive ? 36 : 28

      const icon = L.divIcon({
        className: '',
        html: `<div style="
          width:${size}px;height:${size}px;
          background:${color};
          border-radius:50% 50% 50% 0;
          transform:rotate(-45deg);
          border:3px solid white;
          box-shadow:0 2px 8px rgba(0,0,0,0.35);
        "></div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size],
      })

      const marker = L.marker([loc.lat, loc.lng], { icon })
        .addTo(map)
        .bindPopup(`<b>${loc.name}</b>`)

      markersRef.current.push(marker)
      latlngs.push([loc.lat, loc.lng])
    })

    if (latlngs.length > 1) {
      const poly = L.polyline(latlngs, { color: '#3b82f6', weight: 4, opacity: 0.75, dashArray: '8 6' }).addTo(map)
      polylineRef.current = poly
      map.fitBounds(poly.getBounds(), { padding: [40, 40] })
    } else if (latlngs.length === 1) {
      map.setView(latlngs[0] as L.LatLngExpression, 15)
    }
  }, [locations, activeIdx])

  return <div ref={containerRef} className="w-full h-full rounded-xl overflow-hidden border border-gray-200" />
}

// ── Timeline Card ────────────────────────────────────────────────────────
function Card({ card, isActive, onClick }: { card: TimelineCard; isActive: boolean; onClick: () => void }) {
  const CFG: Record<string, { icon: string; color: string }> = {
    depart:  { icon: '🚀', color: 'border-blue-400 bg-blue-50' },
    transit: { icon: '🚌', color: 'border-amber-400 bg-amber-50' },
    service: { icon: '📋', color: 'border-green-400 bg-green-50' },
    class:   { icon: '📚', color: 'border-purple-400 bg-purple-50' },
    arrive:  { icon: '🎉', color: 'border-emerald-400 bg-emerald-50' },
  }
  const cfg = CFG[card.type] ?? CFG.service
  const conflictCls = card.conflict ? 'border-red-400 bg-red-50' : cfg.color

  return (
    <div
      onClick={onClick}
      className={`rounded-xl border-l-4 p-3.5 cursor-pointer transition-all ${conflictCls} ${isActive ? 'shadow-md scale-[1.01]' : 'hover:shadow-sm'}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{card.conflict ? '⚠️' : cfg.icon}</span>
          <div>
            <div className="font-semibold text-gray-800 text-sm">{card.title}</div>
            <div className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
              <Clock size={10} />
              {card.time}{card.end_time ? ` – ${card.end_time}` : ''}
              {card.duration_min > 0 && <span className="text-gray-400 ml-1">({card.duration_min}min)</span>}
            </div>
          </div>
        </div>
        {card.conflict && (
          <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium shrink-0">⚠ Conflict</span>
        )}
      </div>
      <div className="mt-1.5 text-xs text-gray-600 flex items-start gap-1">
        <MapPin size={10} className="mt-0.5 shrink-0 text-gray-400" />
        {card.location}
      </div>
      {card.description && <p className="mt-1 text-xs text-gray-500 line-clamp-2">{card.description}</p>}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────
const QUICK_PROMPTS = [
  '我今天要办理宿舍入住，请帮我规划路线',
  'Help me plan dorm check-in: Blk 365 → UTown → EA → YIH → KR Hall',
  'I need to visit UTown, EA, YIH and Kent Ridge Hall today',
]

// Default NUS POIs for initial map (no API call needed)
const DEFAULT_LOCATIONS: Location[] = [
  { key: 'start',           name: 'Blk 365 Clementi Ave 2',        lat: 1.3143, lng: 103.7653, type: 'origin' },
  { key: 'utown',           name: 'UTown Residential College',      lat: 1.3044, lng: 103.7739, type: 'checkin_office' },
  { key: 'ea',              name: 'EA (Engineering Annex)',          lat: 1.2998, lng: 103.7720, type: 'checkin_office' },
  { key: 'yih',             name: 'YIH (Yusof Ishak House)',         lat: 1.2977, lng: 103.7735, type: 'checkin_office' },
  { key: 'kent_ridge_hall', name: 'Kent Ridge Hall',                 lat: 1.2941, lng: 103.7801, type: 'destination' },
]

export default function CampusPage() {
  const [input, setInput] = useState('')
  const [startTime, setStartTime] = useState('09:00')
  const [loading, setLoading] = useState(false)
  const [steps, setSteps] = useState<string[]>([])
  const [result, setResult] = useState<RouteResult | null>(null)
  const [activeCardIdx, setActiveCardIdx] = useState(0)
  const [mapLocations, setMapLocations] = useState<Location[]>(DEFAULT_LOCATIONS)

  const handlePlan = async (requestText?: string) => {
    const req = requestText ?? input.trim()
    if (!req || loading) return
    setLoading(true)
    setSteps([])
    setResult(null)
    setActiveCardIdx(0)

    try {
      const resp = await fetch('/api/campus/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: req, start_time: startTime }),
      })

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'step') {
              setSteps(prev => [...prev, data.message])
            } else if (data.type === 'result') {
              setResult(data)
              setMapLocations(data.route.locations)
            } else if (data.type === 'error') {
              setSteps(prev => [...prev, `❌ ${data.message}`])
            }
          } catch {}
        }
      }
    } catch (e: any) {
      setSteps(prev => [...prev, `❌ Network error: ${e.message}`])
    } finally {
      setLoading(false)
    }
  }

  const handleCardClick = (idx: number) => {
    setActiveCardIdx(idx)
  }

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      {/* ── Left: Map ── */}
      <div className="w-[55%] flex flex-col p-4 gap-3">
        <div className="flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-lg font-bold text-nus-blue flex items-center gap-2">
              <Navigation size={20} />
              Campus Route Planner
            </h1>
            <p className="text-xs text-gray-400">AI-powered NUS navigation with schedule conflict detection</p>
          </div>
          {result && (
            <div className="flex items-center gap-1.5 bg-green-50 border border-green-200 rounded-lg px-3 py-1.5">
              <CheckCircle size={14} className="text-green-600" />
              <span className="text-xs text-green-700 font-medium">{result.route.total_min} min total</span>
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0">
          <LeafletMap locations={mapLocations} activeIdx={activeCardIdx} />
        </div>

        {result && (
          <div className="flex gap-2 flex-wrap shrink-0">
            {result.skills_used.map(skill => (
              <span key={skill} className="text-xs bg-nus-blue/10 text-nus-blue px-2 py-1 rounded-full font-medium">
                🔧 {skill}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Right: Chat + Timeline ── */}
      <div className="flex-1 flex flex-col border-l border-gray-200 bg-white overflow-hidden">
        {/* Input */}
        <div className="p-4 border-b border-gray-100 shrink-0">
          <div className="flex gap-2 mb-2">
            <input
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-nus-blue/30 focus:border-nus-blue"
              placeholder="e.g. 我今天要办理宿舍入住，请帮我规划路线..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !loading && handlePlan()}
            />
            <input
              type="time"
              className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-nus-blue/30"
              value={startTime}
              onChange={e => setStartTime(e.target.value)}
            />
            <button
              onClick={() => handlePlan()}
              disabled={loading || !input.trim()}
              className="bg-nus-blue text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-40 flex items-center gap-1.5 transition-colors"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              Plan
            </button>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {QUICK_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => { setInput(p); handlePlan(p) }}
                className="text-xs bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-full px-2.5 py-1 text-gray-600 transition-colors"
              >
                {p.length > 38 ? p.slice(0, 38) + '…' : p}
              </button>
            ))}
          </div>
        </div>

        {/* Agent steps */}
        {(loading || steps.length > 0) && !result && (
          <div className="p-4 border-b border-gray-100 bg-gray-50 shrink-0">
            <div className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Agent Processing</div>
            <div className="space-y-1.5 max-h-36 overflow-y-auto">
              {steps.map((s, i) => (
                <div key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                  <span className="text-gray-400 shrink-0">{i + 1}.</span>{s}
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-1.5 text-xs text-nus-blue">
                  <Loader2 size={11} className="animate-spin" />Processing...
                </div>
              )}
            </div>
          </div>
        )}

        {/* AI Narrative */}
        {result && (
          <div className="p-4 border-b border-gray-100 bg-blue-50 shrink-0">
            <div className="flex items-center gap-1.5 mb-1.5">
              <BookOpen size={14} className="text-nus-blue" />
              <span className="text-xs font-semibold text-nus-blue">AI Route Summary</span>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{result.narrative}</p>
          </div>
        )}

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto p-4">
          {result ? (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                Route Timeline · {result.timeline.length} steps
              </div>
              {result.timeline.map((card, idx) => (
                <div key={card.id} className="flex gap-2">
                  <div className="flex flex-col items-center">
                    <div className={`w-2 h-2 rounded-full mt-4 shrink-0 ${
                      card.conflict ? 'bg-red-500' :
                      card.type === 'class' ? 'bg-purple-500' :
                      card.type === 'service' ? 'bg-green-500' :
                      card.type === 'arrive' ? 'bg-emerald-500' : 'bg-blue-500'
                    }`} />
                    {idx < result.timeline.length - 1 && <div className="w-px flex-1 bg-gray-200 mt-1" />}
                  </div>
                  <div className="flex-1 pb-2">
                    <Card card={card} isActive={activeCardIdx === idx} onClick={() => handleCardClick(idx)} />
                  </div>
                </div>
              ))}
            </div>
          ) : !loading && steps.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-14 h-14 bg-nus-blue/10 rounded-2xl flex items-center justify-center mb-4">
                <Navigation size={28} className="text-nus-blue" />
              </div>
              <h3 className="text-base font-semibold text-gray-700 mb-1">Campus Route Planner</h3>
              <p className="text-sm text-gray-400 max-w-xs leading-relaxed">
                Tell me where you need to go on campus. I'll check your schedule, look up office hours, and plan an optimized route.
              </p>
              <div className="mt-4 space-y-1.5 w-full max-w-xs">
                {QUICK_PROMPTS.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => { setInput(p); handlePlan(p) }}
                    className="block w-full text-left text-xs text-nus-blue hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-2 rounded-lg transition-colors"
                  >
                    <ChevronRight size={10} className="inline mr-1" />{p}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
