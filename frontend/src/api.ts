// API base URL — empty string = same origin (local dev via Vite proxy)
// On Railway production, set VITE_API_URL to your backend service URL
export const API_BASE = import.meta.env.VITE_API_URL ?? ''

// WebSocket base
export const WS_BASE = API_BASE
  ? API_BASE.replace(/^https?/, (p) => (p === 'https' ? 'wss' : 'ws'))
  : ''
