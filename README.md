# NUS Campus Intelligent Assistant

> A multi-agent AI system built for NUS students — powered by **OpenClaw** (agent orchestration), **WaveSpeed AI** (LLM + Vision), and **ChromaDB** (RAG knowledge base).

---

## Features

### Knowledge Q&A
Ask anything about NUS in natural language. A hybrid RAG pipeline combines ChromaDB semantic search with BM25 keyword search to retrieve relevant campus knowledge, then streams answers via WaveSpeed AI (Gemini 2.5 Flash). Supports agent intent detection — asking about Canvas, jobs, or your syllabus triggers the corresponding agent automatically.

### Schedule Agent
- **Canvas Sync** — Fetches all assignments and announcements from NUS Canvas LMS using your personal access token. AI summarizes announcements automatically.
- **Syllabus Vision** — Upload a syllabus photo or PDF; WaveSpeed Vision AI extracts all exam dates, deadlines, and project milestones and adds them to your schedule.
- **Calendar Export** — Download a `.ics` file importable into any calendar app, or push all events directly to **Google Calendar** via OAuth (one-time authorization, then fully automatic). Every event includes a 24-hour email reminder and 1-hour popup alert.
- **Email Reminder** — Send a formatted HTML schedule summary with a `.ics` attachment to any email address.
- **Event Management** — Delete individual events or clear all events from the timeline.

### Job Agent
- Searches LinkedIn Jobs for matching positions using Playwright browser automation.
- Uses WaveSpeed AI to score each job listing against your uploaded resume (0–100 match score).
- Auto-applies to high-scoring jobs via LinkedIn Easy Apply.
- Streams real-time progress via SSE (Server-Sent Events) to the Agent Console.
- Falls back to demo mode with realistic mock data when LinkedIn anti-bot detection triggers.

### Campus Route Planner
Plan campus routes in natural language (e.g. *"I need to complete dormitory check-in today"*). The agent:
1. Parses your destination stops from the request
2. Checks your calendar for class conflicts (`get_calendar_events`)
3. Looks up office hours and procedures via RAG (`search_knowledge_base`)
4. Calculates walking/bus times between NUS locations (`calculate_route_matrix`)
5. Builds a step-by-step timeline with conflict warnings
6. Renders the full route on an interactive OpenStreetMap map

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM + Vision | WaveSpeed AI (Google Gemini 2.5 Flash) |
| Agent Framework | OpenClaw |
| Backend | FastAPI + SQLAlchemy + aiosqlite (Python 3.11) |
| Vector DB | ChromaDB + sentence-transformers (all-MiniLM-L6-v2) |
| Keyword Search | BM25 (rank-bm25) — hybrid RAG with RRF fusion |
| Frontend | React 18 + TypeScript + Tailwind CSS + Vite |
| Map | Leaflet + OpenStreetMap (no API key required) |
| Browser Automation | Playwright (Chromium) |
| Calendar | Google Calendar API OAuth2 + iCalendar (.ics) |
| Email | Gmail SMTP via aiosmtplib |
| PDF Processing | PyMuPDF |

---

## Project Structure

```
AI_agent/
├── backend/
│   └── app/
│       ├── agents/
│       │   ├── canvas_agent/          # Canvas LMS sync
│       │   ├── job_agent/             # LinkedIn search + auto-apply
│       │   │   └── tools/
│       │   │       ├── linkedin_searcher.py
│       │   │       ├── linkedin_browser.py
│       │   │       └── resume_parser.py
│       │   ├── knowledge_agent/       # RAG Q&A
│       │   │   ├── rag_service.py     # Hybrid BM25 + semantic retrieval
│       │   │   ├── ingestion/         # NUS web crawler
│       │   │   └── vectorstore/       # ChromaDB client
│       │   ├── syllabus_agent/        # Vision AI date extraction
│       │   ├── schedule_agent/        # ICS builder + email + Google Calendar
│       │   │   ├── ics_builder.py
│       │   │   ├── email_reminder.py
│       │   │   └── gcal_pusher.py
│       │   ├── campus_agent/          # Route planning
│       │   │   ├── skills.py          # get_calendar_events, search_kb, route_matrix
│       │   │   └── planner.py         # Agent loop + timeline builder
│       │   └── orchestrator.py
│       ├── routers/                   # FastAPI route handlers
│       ├── services/
│       │   └── wavespeed_service.py   # Unified WaveSpeed AI client
│       ├── models/                    # SQLAlchemy ORM models
│       └── main.py
├── frontend/
│   └── src/
│       └── pages/
│           ├── ChatPage.tsx           # Knowledge Q&A (WebSocket streaming)
│           ├── SchedulePage.tsx       # Schedule Agent
│           ├── JobsPage.tsx           # Job Agent console
│           └── CampusPage.tsx         # Route planner + map
├── openclaw/skills/                   # OpenClaw SKILL.md definitions
├── scripts/
│   └── ingest_knowledge.py            # Run once to populate ChromaDB
├── .env.example
└── docker-compose.yml
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Conda (recommended) or virtualenv

### 1. Clone and configure

```bash
git clone https://github.com/wangyisong-njust/ai_agent.git
cd ai_agent
cp .env.example backend/.env
# Fill in your API keys in backend/.env
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

### 4. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` to verify the API is running.

### 5. Ingest the NUS knowledge base (first run only)

```bash
cd ..
python scripts/ingest_knowledge.py
```

This crawls NUS websites and populates ChromaDB. Takes 3–5 minutes. Only needed once.

### 6. Start the frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`

---

## Environment Variables

Copy `.env.example` to `backend/.env` and fill in:

| Variable | Description |
|---|---|
| `WAVESPEED_API_KEY` | WaveSpeed AI API key |
| `WAVESPEED_LLM_MODEL` | Model name (default: `google/gemini-2.5-flash`) |
| `CANVAS_ACCESS_TOKEN` | NUS Canvas personal access token |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (for Calendar push) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `SMTP_USER` | Gmail address for email reminders |
| `SMTP_PASSWORD` | Gmail app password |
| `SECRET_KEY` | Random secret for the app |

To get your Canvas token: Canvas → Account → Settings → Approved Integrations → New Access Token

---

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| `WS` | `/api/knowledge/ws/chat` | Streaming Q&A chat |
| `POST` | `/api/schedule/sync-canvas` | Sync Canvas assignments |
| `POST` | `/api/schedule/upload-syllabus` | Extract events from syllabus |
| `GET` | `/api/schedule/download-ics` | Download `.ics` calendar file |
| `POST` | `/api/schedule/gcal/push` | Push events to Google Calendar |
| `POST` | `/api/schedule/send-email` | Send schedule email |
| `DELETE` | `/api/schedule/events` | Clear all events |
| `DELETE` | `/api/schedule/events/{source}/{id}` | Delete single event |
| `POST` | `/api/jobs/auto-apply` | Launch Job Agent (SSE stream) |
| `POST` | `/api/campus/plan` | Plan campus route (SSE stream) |
| `GET` | `/api/campus/locations` | Get NUS POI locations |
| `GET` | `/api/prefs` | Load saved user preferences |
| `POST` | `/api/prefs` | Save user preferences |

---

## Powered By

- [WaveSpeed AI](https://wavespeed.ai) — LLM inference and Vision AI
- [OpenClaw](https://openclaw.dev) — Multi-agent orchestration framework
- [ChromaDB](https://www.trychroma.com) — Vector database for RAG
