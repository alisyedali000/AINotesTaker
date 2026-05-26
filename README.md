# Voice Controlled Task Manager

A production-quality MVP where users manage tasks entirely through natural voice conversation — no typing, forms, or manual CRUD buttons.

## Architecture

```
┌─────────────────┐     WebSocket (audio + JSON)     ┌──────────────────────┐
│  Next.js Client │ ◄──────────────────────────────► │  FastAPI Backend     │
│  (Vercel)       │                                  │  (Render)            │
└────────┬────────┘                                  └──────────┬───────────┘
         │ Microphone / Speaker                                 │
         │                                                      ├── STT (gpt-4o-mini-transcribe)
         │                                                      ├── LLM (gpt-4.1-mini)
         │                                                      ├── TTS (gpt-4o-mini-tts)
         │                                                      └── SQLite (SQLAlchemy)
```

### Voice flow

1. User holds microphone → browser streams audio chunks over WebSocket
2. On release → backend runs STT → LLM returns structured JSON action
3. Backend executes task CRUD → generates conversational TTS response
4. TTS audio streams back to browser for playback
5. If user speaks during TTS → **interrupt** cancels playback and processes new speech

### Project structure

```
UrbanGround/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── websocket.py     # Real-time voice endpoint
│   │   ├── agents/
│   │   │   ├── conversation.py  # Orchestration layer
│   │   │   └── session.py       # In-memory context
│   │   ├── services/
│   │   │   ├── openai_service.py
│   │   │   └── task_service.py
│   │   ├── models/
│   │   │   └── task.py
│   │   ├── database/
│   │   │   └── connection.py
│   │   └── schemas/
│   ├── requirements.txt
│   └── render.yaml
├── frontend/
│   ├── app/
│   ├── components/
│   └── hooks/
│       └── useVoiceWebSocket.ts
└── README.md
```

## Features

- **Voice CRUD**: Create, read, update, delete tasks via conversation
- **Semantic references**: "Move my evening workout", "change the second one"
- **Delete confirmation**: Always confirms before destructive actions
- **Multiple tasks**: Batch create in one utterance
- **Interruption handling**: Stop TTS immediately when user speaks
- **Context memory**: Recent tasks, pending confirmations, conversation history
- **Graceful failures**: STT/LLM/TTS/WebSocket errors recover conversationally

## Prerequisites

- Node.js 18+
- Python 3.11+
- OpenAI API key with access to:
  - `gpt-4o-mini-transcribe` (STT)
  - `gpt-4.1-mini` (reasoning)
  - `gpt-4o-mini-tts` (TTS)

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
python run.py
```

API runs at `http://localhost:8000`  
WebSocket: `ws://localhost:8000/ws/voice`

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Default WS URL points to localhost:8000
npm run dev
```

Open `http://localhost:3000`

### 3. Try it

1. Allow microphone access
2. Hold the mic button and say: *"Create a task for gym tomorrow at 7 AM"*
3. Release — wait for the assistant to respond
4. Ask: *"What's my agenda tomorrow?"*
5. Say: *"Move my gym task to 8 AM"*
6. To delete: *"Delete the gym task"* → confirm with *"Yes"*

## WebSocket protocol

**Client → Server**

| Type | Description |
|------|-------------|
| `audio_chunk` | Base64-encoded audio (streamed while recording) |
| `audio_end` | End of utterance → trigger STT + LLM |
| `interrupt` | Cancel TTS, start new turn |
| `ping` | Keep-alive |

**Server → Client**

| Type | Description |
|------|-------------|
| `transcript` | User or assistant text |
| `tts_start` / `audio_chunk` / `tts_end` | Streamed MP3 response |
| `tts_cancelled` | TTS interrupted |
| `status` | `listening` \| `processing` \| `speaking` |

## LLM actions

The LLM returns structured JSON:

```json
{
  "action": "create_task",
  "title": "Gym",
  "datetime": "2026-05-27T07:00:00",
  "response_text": "Got it — I've scheduled your gym session for 7 AM tomorrow."
}
```

Supported actions: `create_task`, `read_tasks`, `update_task`, `delete_task`, `confirm_delete`, `ask_followup`, `clarify`

## Deployment

### Backend (Render)

1. Push repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect repo, set root directory to `backend`
4. Build: `pip install -r requirements.txt`
5. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Environment variables:
   - `OPENAI_API_KEY`
   - `CORS_ORIGINS=https://your-app.vercel.app`
7. Note your Render URL, e.g. `https://voice-api.onrender.com`

> **Note**: Render free tier sleeps; first request may be slow. WebSockets require a web service (not static site).

### Frontend (Vercel)

1. Import repo on [Vercel](https://vercel.com)
2. Set root directory to `frontend`
3. Environment variables:
   - `NEXT_PUBLIC_WS_URL=wss://voice-api.onrender.com/ws/voice`
   - `NEXT_PUBLIC_API_URL=https://voice-api.onrender.com`
4. Deploy

Update backend `CORS_ORIGINS` with your Vercel URL.

## Environment variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `DATABASE_URL` | Default: `sqlite+aiosqlite:///./tasks.db` |
| `CORS_ORIGINS` | Comma-separated allowed origins |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_WS_URL` | WebSocket URL |
| `NEXT_PUBLIC_API_URL` | REST base URL (health checks) |

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), React, TailwindCSS |
| Backend | Python FastAPI, WebSockets |
| AI | OpenAI STT, gpt-4.1-mini, TTS |
| Database | SQLite + SQLAlchemy (async) |
| Deploy | Vercel + Render |

## License

MIT — Urban Ground take-home assessment.
