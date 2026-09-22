# Concurrent Data Ingestion Pipeline — Merged Build

A hackathon project that ingests data from multiple mock sources **concurrently**,
validates → normalizes → deduplicates it, persists it in PostgreSQL, and exposes it
through a REST API + WebSocket to a live React dashboard.

This is the **merged, integrated codebase** combining all four team members' work:

| Member | Contribution | Status in this merge |
|---|---|---|
| Member 1 | FastAPI backend, async orchestrator, REST API, WebSocket | ✅ integrated |
| Member 2 | Mock sources A/B/C, validation, normalization, deduplication | ✅ integrated |
| Member 3 | PostgreSQL + SQLAlchemy persistence, statistics | ✅ integrated |
| Member 4 | React + TypeScript dashboard, charts, live WebSocket UI | ✅ integrated |

No manual conflict resolution was needed: each member's zip was a strict,
additive superset of the previous one (member3's backend already contained
member1's and member2's code, wired together), and the frontend was built
independently against the documented API contract. See **"How the merge was
done"** near the bottom for exactly what was checked.

```
Mock Source A ─┐
Mock Source B ─┼──> Concurrent Ingestion ──> Validation ──> Normalization
Mock Source C ─┘                                                  │
                                                                    ▼
                                                            Deduplication
                                                                    │
                                                                    ▼
                                                              PostgreSQL
                                                                    │
                                                      ┌─────────────┴─────────────┐
                                                      ▼                           ▼
                                                  REST API                   WebSocket
                                                      │                           │
                                                      └─────────────┬─────────────┘
                                                                    ▼
                                                           React Dashboard
```

---

## 1. Project layout

```
concurrent-data-ingestion-pipeline/
├── README.md                    # this file
├── MEMBER1_BACKEND.md           # Member 1's full backend docs + API reference
├── MEMBER2_DATA_PIPELINE.md     # Member 2's sources/validation/normalization/dedup docs
├── MEMBER3_DATABASE.md          # Member 3's PostgreSQL schema + setup docs
├── MEMBER4_FRONTEND.md          # Member 4's frontend docs
├── .env.example                 # backend environment template
├── .gitignore
├── backend/                     # FastAPI + SQLAlchemy backend
│   ├── main.py                  # app entrypoint (uvicorn target)
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── core/                # config, logging
│   │   ├── sources/              # Mock Source A / B / C
│   │   ├── ingestion/             # orchestrator, validator, normalizer, deduplicator, retry
│   │   ├── database/              # SQLAlchemy engine/session + ORM models
│   │   ├── repositories/          # Repository protocol + InMemory & Postgres implementations
│   │   ├── services/               # ingestion_service, stats_service, dependency wiring
│   │   ├── schemas/                # Pydantic response models
│   │   └── api/                     # REST routes + WebSocket endpoint
│   └── tests/                    # 62 pytest tests
└── frontend/                    # React 18 + TypeScript + Vite dashboard
    ├── src/
    │   ├── components/           # StatsPanel, SourceGrid, PipelineFlow, charts, tables, etc.
    │   ├── pages/Dashboard.tsx   # main page: data loading + WebSocket wiring
    │   ├── services/              # api.ts (REST), websocket.ts, mockData.ts
    │   ├── hooks/useWebSocket.ts
    │   ├── types/dashboard.ts    # mirrors backend Pydantic schemas
    │   └── config.ts             # reads VITE_* env vars
    ├── .env.example
    ├── package.json
    └── vite.config.ts
```

---

## 2. What the application does (the idea, end to end)

1. Three **mock data sources** (Source A, B, C) each simulate an external
   system with its own latency/failure characteristics.
2. Hitting **"Run Ingestion"** (or `POST /api/ingest`) kicks off an
   **async, concurrent** fetch from all three sources at once
   (`asyncio.gather`), each with its own timeout and bounded retry.
3. Every incoming record is **validated** (schema/field checks), then
   **normalized** into one canonical shape regardless of source, then
   **deduplicated** using a SHA-256 hash (`record_hash`) — first in-memory
   during the run, then again at the database level via a
   `UNIQUE` constraint + `ON CONFLICT DO NOTHING`, as a second safety net.
4. Clean, deduplicated records are **persisted to PostgreSQL**
   (falls back to an in-memory store automatically if no database is
   configured — see §4).
5. Every step of a run emits an event (`INGESTION_STARTED`,
   `SOURCE_STARTED`, `SOURCE_COMPLETED`, `SOURCE_FAILED`,
   `INGESTION_COMPLETED`) over a **WebSocket** (`/ws`).
6. The **React dashboard** shows live stats (received/processed/
   duplicates/failed), per-source health, a pipeline diagram, a run
   history chart, a paginated records table, and a live activity feed —
   all updating in real time as a run happens, no page refresh.

---

## 3. Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.10+ | backend |
| Node.js | 18+ (20+ recommended) | frontend |
| npm | comes with Node | frontend package management |
| PostgreSQL | 14+ | optional — persistent storage (app runs without it) |
| Docker | optional | easiest way to run Postgres locally |

You do **not** need Postgres or Docker to see the whole app working end to
end — without `DATABASE_URL` set, the backend automatically falls back to
an in-memory store, and the frontend has its own mock-data mode. Both are
useful for a quick demo; use real Postgres for anything you want to persist.

---

## 4. Setup & running — backend

```bash
cd backend
pip install -r requirements.txt --break-system-packages
cp ../.env.example .env        # then edit .env as needed (see below)
uvicorn main:app --reload
```

Backend runs at **http://localhost:8000**. Interactive API docs (Swagger
UI) are auto-generated at **http://localhost:8000/docs**.

### Running with an in-memory store (zero setup)

Leave `DATABASE_URL` empty in `.env` (or don't create `.env` at all — every
setting has a working default). The API, WebSocket, and dashboard all work
exactly the same; data just isn't persisted across restarts.

### Running with PostgreSQL (persistent storage)

**Option A — Docker (fastest):**
```bash
docker run --name ingestion-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ingestion_db -p 5432:5432 -d postgres:16
```
Then in `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion_db
```

**Option B — Supabase (hosted, no local install):**
Create a project, copy its connection string (`postgres://...` or
`postgresql://...` both work — auto-normalized) into `DATABASE_URL`.

Either way, **no manual migration step is needed** — tables are created
automatically on startup (`Base.metadata.create_all()`).

### Key `.env` variables (backend)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | *(empty → in-memory)* | PostgreSQL connection string |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed frontend origins |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `INGESTION_TIMEOUT` | `5` | per-source timeout, seconds |
| `MAX_RETRIES` | `3` | attempts per source, including the first |
| `RETRY_DELAY` | `0.5` | base delay between retries, seconds |
| `PORT` | `8000` | server port |
| `TEST_DATABASE_URL` | *(empty)* | separate disposable DB for database tests only |

---

## 5. Setup & running — frontend

```bash
cd frontend
npm install
cp .env.example .env     # adjust only if the backend runs elsewhere
npm run dev
```

Opens at **http://localhost:5173**, which matches the backend's default
`CORS_ORIGINS`. With both backend and frontend running, open the dashboard
in your browser and click **"Run Ingestion"** to trigger a live run and
watch the dashboard update in real time.

### Key `.env` variables (frontend)

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | backend REST base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | backend WebSocket URL |
| `VITE_USE_MOCK_DATA` | `false` | run the whole UI on canned data, **no backend needed** |

Set `VITE_USE_MOCK_DATA=true` to explore every screen of the dashboard
immediately with zero backend setup — useful for a quick look at the UI.
Set it back to `false` (and start the backend) to see it live.

### Building for production

```bash
npm run build     # tsc -b && vite build, outputs to frontend/dist
npm run preview   # serve that production build locally
```

---

## 6. Running order (quick start, from nothing)

```bash
# Terminal 1 — backend, no database needed to try it out
cd backend
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
cp .env.example .env
npm run dev
```
Open http://localhost:5173, click **Run Ingestion**, watch it happen live.
Open http://localhost:8000/docs to explore/call the REST API directly.

---

## 7. Features tour

**Dashboard header** — title, a LIVE/DISCONNECTED pill reflecting the real
WebSocket state (never hardcoded), a Refresh button, and the Run Ingestion
button (shows "Running…" while a run is in progress).

**Stats panel** — Received / Processed / Duplicates / Failed counts, plus
the most recent run's status and duration.

**Pipeline flow diagram** — an SVG schematic of Source A/B/C flowing
concurrently into validation → normalization → deduplication → PostgreSQL
→ dashboard, with live per-source health dots.

**Source grid** — one card per source: health status
(HEALTHY / DEGRADED / DOWN / UNKNOWN), records received/processed,
duplicate count, last success/failure timestamps.

**Ingestion chart** — a bar chart (Recharts) of the last 10 runs' duration.

**Recent runs table** — newest-first list of ingestion runs with status
and totals.

**Records table** — paginated table of processed, deduplicated records.

**Live activity feed** — rolling log of the last 12 WebSocket events as
they happen (`INGESTION_STARTED`, `SOURCE_STARTED`, `SOURCE_COMPLETED`,
`SOURCE_FAILED`, `INGESTION_COMPLETED`).

**Resilience states** — loading skeletons, empty states ("no data yet"),
and error states with retry, plus graceful behavior if the backend goes
down mid-session (dashboard shows DISCONNECTED, REST data stays visible).

---

## 8. REST API reference (summary)

Full request/response shapes: `MEMBER1_BACKEND.md` and
`backend/app/schemas/responses.py`. Interactive docs at `/docs` once the
backend is running.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | health check |
| POST | `/api/ingest` | trigger a new concurrent ingestion run |
| GET | `/api/stats` | aggregate stats (received/processed/duplicates/failed) |
| GET | `/api/sources` | per-source health/status |
| GET | `/api/records?page=&page_size=&source=` | paginated processed records |
| GET | `/api/runs` | recent ingestion runs (newest first) |
| GET | `/api/runs/{run_id}` | one run's full detail |
| WS | `/ws` | live ingestion event stream |

---

## 9. Testing

**Backend (pytest, 62 tests total):**

```bash
cd backend
pip install -r requirements.txt --break-system-packages
pytest -v
```

| File | Covers |
|---|---|
| `test_api.py` | REST endpoints |
| `test_websocket.py` | WebSocket event stream |
| `test_orchestrator.py` | concurrency, timeouts, retry — includes a timing-based proof that sources run concurrently, not sequentially |
| `test_sources.py` | Mock Source A/B/C behavior |
| `test_validator.py` | record validation rules |
| `test_normalizer.py` | canonical record normalization |
| `test_deduplicator.py` | hash-based deduplication |
| `test_pipeline_integration.py` | end-to-end pipeline flow |
| `test_database.py` | PostgreSQL repository — **skipped automatically** unless `TEST_DATABASE_URL` is set and reachable |

To also run the database tests, point `TEST_DATABASE_URL` at a
**separate, disposable** database (never your real/Supabase one):

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion_test
pytest tests/test_database.py -v
```
Without it, `pytest` still runs green on a fresh clone before Postgres is
set up — those tests are skipped, not failed.

**Frontend:**

There's no unit-test suite for the frontend (not part of the original
scope); verify it manually with the checklist in `MEMBER4_FRONTEND.md`
§12 — the essentials are:

```bash
cd frontend
npm install
npm run build     # TypeScript + build must succeed with no errors
npm run lint       # ESLint
npm run dev         # then exercise the app in the browser:
```
- Loads against a running backend (`VITE_USE_MOCK_DATA=false`)
- Loads against mock data with no backend running (`VITE_USE_MOCK_DATA=true`)
- Stats/sources/runs/records all populate
- "Run Ingestion" triggers a live-updating run via WebSocket
- Stopping the backend shows "DISCONNECTED" and REST data stays visible
- No horizontal scroll on a narrow/mobile viewport

---

## 10. Deployment notes

- **Backend**: deployable as-is to any container/PaaS host (e.g. Render) —
  it already reads `PORT` from the environment and binds `0.0.0.0`. Set
  `DATABASE_URL` and `CORS_ORIGINS` (include your deployed frontend's
  origin) as environment variables on the host.
- **Frontend**: static Vite build, deployable to Vercel/Netlify/any static
  host. Set `VITE_API_URL` to the deployed backend's HTTPS URL and
  `VITE_WS_URL` to its WebSocket URL using `wss://` (required once the
  dashboard is served over HTTPS — mixed `ws://` content is blocked by
  browsers). Set `VITE_USE_MOCK_DATA=false`.

---

## 11. How the merge was done

The four uploaded zips were not independent, potentially-conflicting
copies — they were **sequential, additive snapshots** of the same
backend repo (member1 → member2 → member3 each added files/wiring on top
of the previous one, with clear "Member N wires in here" comments), plus
a separately-built frontend (member4) written against the documented API
contract rather than against the backend code directly.

Concretely, before merging:
- Diffed every file member2 and member3 had in common — the only changes
  were the three additive, well-commented edits member3's own docs
  described (`dependencies.py` wiring in `PostgresRepository` with an
  automatic in-memory fallback, and `main.py` calling `init_db()` /
  `check_database_connection()` at startup, both guarded so a missing
  database never blocks the API from starting). No competing or
  contradictory changes existed between any two members' versions of the
  same file.
- Confirmed member3's backend is a strict superset containing all of
  member1's and member2's code plus member3's own database layer — so it
  was used as the single backend source, rather than hand-splicing three
  trees together.
- Cross-checked the frontend's documented REST/WebSocket contract
  (`MEMBER4_FRONTEND.md`) against the backend's actual routes and
  response schemas (`app/api/routes.py`, `app/schemas/responses.py`) —
  endpoints, field names (`run_id` not `id`, `records` not `items`,
  `record_hash`, source status enum), and default ports/CORS origin
  (`5173` ↔ `http://localhost:5173`) all match with no changes needed on
  either side.
- Compiled every backend `.py` file (`python -m py_compile`) to confirm
  there are no syntax errors or broken imports after the merge.

No files were dropped, no code was rewritten, and nothing needed manual
conflict resolution — the merge is a direct combination of member3's full
backend tree and member4's full frontend tree.
