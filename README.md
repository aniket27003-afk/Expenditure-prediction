# AI-Powered Smart Expense & Spending Analyzer Using LLM-Based Transaction Understanding and Personalized Financial Insights

Per `PRD — Smart Expense & Spending Analyzer.md`. No ML training — **LLM for reasoning, Python/SQL for numbers, PostgreSQL/SQLite for storage**.

## Architecture

```
Web UI (React) → FastAPI → Transaction Parser → Grok LLM → DB
→ Python/pandas analytics → summary → Grok LLM → insights → Dashboard
```

## Project layout

```
ProjectOne/
├── .env / .env.example        ← ★ PUT YOUR GROQ KEY HERE
├── backend/
│   ├── requirements.txt
│   └── app/ (config, database, models, schemas, llm, analytics, main)
├── frontend/ (React + Vite + Recharts)
└── docker-compose.yml         ← optional PostgreSQL
```

## 1. Put your keys in `.env`

Open the root **`.env`** file and set:

```env
GROQ_API_KEY=gsk-your-key-here     # from https://console.groq.com/keys
```

Other keys in `.env` (all optional, sensible defaults included):

| Key | Default | Purpose |
|---|---|---|
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq endpoint (OpenAI-compatible) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | quality; use `openai/gpt-oss-20b` for cheap/fast |
| `GROQ_TIMEOUT` | `30` | API timeout (s) |
| `LLM_FALLBACK_TO_RULES` | `true` | offline rule-based parser when key missing |
| `DATABASE_URL` | `sqlite:///./expenses.db` | swap to `postgresql+psycopg2://…` for prod |
| `CORS_ORIGINS` | `http://localhost:5173,…` | frontend origins |
| `VITE_API_URL` | empty (dev proxy) | set to backend URL in production |

Without a key the app still runs in **offline mode** (rule-based categorization + heuristic insights).

## 2. Run the backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# docs: http://127.0.0.1:8000/docs
```

## 3. Run the frontend

```powershell
cd frontend
npm install
npm run dev
# app: http://localhost:5173
```

## 4. Try it (MVP flow, PRD §10)

1. Create a user → **Load demo data** (seeds messy PRD examples like `UPI-UBER-TRIP-284`).
2. **Add Expense** → Grok extracts merchant + category → saved to DB.
3. **Dashboard** shows totals, monthly, category pie, trend line, top merchants, recent (all Python/SQL).
4. **Generate AI Insights** → Grok returns spending analysis + anomalies + forecast estimate.

## API quick reference

| Method | Endpoint | Purpose (PRD) |
|---|---|---|
| POST | `/api/users` | create user |
| POST | `/api/parse` | LLM parse only (§4B) |
| POST | `/api/transactions` | add + auto-categorize (§4A–C) |
| GET | `/api/transactions?user_id=` | list |
| GET | `/api/dashboard?user_id=` | stats (§4D) |
| POST | `/api/insights/generate?user_id=` | AI analysis (§4E/F/G) |
| GET | `/api/insights?user_id=` | saved insights |
| POST | `/api/seed?user_id=` | demo data |

## PostgreSQL (per PRD)

```powershell
docker compose up -d
# in .env: DATABASE_URL=postgresql+psycopg://expenses:expenses@localhost:5432/expenses
```

## Deploy

- **Frontend → Vercel:** root `frontend/`, set `VITE_API_URL` to backend URL.
- **Backend → Render/Railway:** root `backend/`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, set `DATABASE_URL` + `GROQ_API_KEY` in dashboard env.
