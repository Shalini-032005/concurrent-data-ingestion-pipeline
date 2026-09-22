# MEMBER4_FRONTEND.md

React dashboard for the Concurrent Data Ingestion Pipeline hackathon
project — Member 4's piece. This document covers what was built, how it
talks to Member 1's backend, and how to run/deploy it.

## 1. Frontend architecture

- **React 18 + TypeScript + Vite**, no server-side rendering.
- One page (`Dashboard`) composed from small, single-purpose components.
- All HTTP calls go through `src/services/api.ts`; nothing else calls
  `fetch` directly.
- One WebSocket connection (`src/services/websocket.ts`, wrapped by
  `src/hooks/useWebSocket.ts`) drives live updates and a local activity
  feed; it never triggers a full page reload.
- Styling is plain CSS (`index.css` for tokens, `App.css` for
  components) — no CSS framework, kept dependency-free per the team
  rules.

## 2. Project structure

```
frontend/
├── src/
│   ├── components/       # Presentational + small-stateful components
│   ├── pages/Dashboard.tsx  # Data loading, WS wiring, layout
│   ├── services/          # api.ts, websocket.ts, mockData.ts
│   ├── hooks/useWebSocket.ts
│   ├── types/dashboard.ts # Mirrors the backend's Pydantic schemas
│   ├── utils/formatters.ts
│   ├── config.ts          # Reads VITE_* env vars, nothing else does
│   ├── App.tsx / main.tsx / index.css / App.css
├── index.html
├── .env.example
├── package.json / vite.config.ts / tsconfig*.json
```

## 3. Components

| Component | Responsibility |
|---|---|
| `DashboardHeader` | Title, LIVE/DISCONNECTED pill, Refresh, Run Ingestion |
| `LiveIndicator` | Renders WebSocket connection state only — never a hardcoded "LIVE" |
| `StatsPanel` / `StatCard` | Received / Processed / Duplicates / Failed + latest run duration & status |
| `PipelineFlow` | SVG schematic showing Source A/B/C flowing concurrently into processing → Postgres → this dashboard |
| `SourceGrid` / `SourceCard` | Per-source health, received/processed/duplicates, last success/failure |
| `IngestionChart` | Recharts bar chart of run duration, last 10 runs |
| `IngestionTable` | Recent runs table, newest first |
| `RecordsTable` | Paginated processed-records table |
| `ActivityFeed` | Rolling log of the last 12 WebSocket events |
| `StatusBadge` | Color **and** text label for every status (never color-only) |
| `LoadingState` / `EmptyState` / `ErrorState` | Skeletons, "no data yet" copy, retry action |

## 4. REST API endpoints used

Base URL: `VITE_API_URL` (no trailing slash).

| Method | Path | Used for |
|---|---|---|
| GET | `/api/stats` | Summary stat strip |
| GET | `/api/sources` | Source grid + pipeline diagram health dots |
| GET | `/api/records?page=&page_size=` | Records table |
| GET | `/api/runs` | Chart + recent runs table |
| GET | `/api/runs/{run_id}` | Available in `api.ts`, not currently called from the UI |
| POST | `/api/ingest` | "Run Ingestion" button |

Response shapes are typed exactly as the backend defines them in
`app/schemas/responses.py` — see `src/types/dashboard.ts`. Notably:
`run_id` (not `id`), `PaginatedRecords.records` (not `items`), and
source health is `HEALTHY | DEGRADED | DOWN | UNKNOWN`.

## 5. WebSocket endpoint

`VITE_WS_URL`, e.g. `ws://localhost:8000/ws` (use `wss://` in
production — see §11). Messages are `IngestionEvent` objects:

```json
{ "event": "SOURCE_COMPLETED", "run_id": 12, "timestamp": "...", "source": "Source A", "records": 10 }
```

`event` is one of `INGESTION_STARTED`, `SOURCE_STARTED`,
`SOURCE_COMPLETED`, `SOURCE_FAILED`, `INGESTION_COMPLETED`. The
dashboard reacts to `INGESTION_STARTED`/`INGESTION_COMPLETED` to
toggle the "Running…" button state and trigger a lightweight REST
refresh once a run finishes (the event itself doesn't carry full
stats/duplicate breakdowns). Every event also becomes one line in the
Live Activity feed. Reconnection uses capped exponential backoff
(1s → 2s → 4s → 8s → 15s).

## 6. Environment variables

See `.env.example`. Copy it to `.env` and adjust:

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_USE_MOCK_DATA=false
```

Only variables prefixed `VITE_` are available to the app — never put
secrets here.

## 7. Mock mode

Set `VITE_USE_MOCK_DATA=true` to run the whole dashboard against
deterministic in-memory data (`src/services/mockData.ts`) with no
backend running — useful while Member 1's API isn't up yet. It must
be `false` for any real demo or deployment; nothing in the build
enforces that automatically, so double-check the deployed env vars.

## 8. Running locally

```bash
cd frontend
npm install
cp .env.example .env    # adjust if the backend runs elsewhere
npm run dev
```

Opens on `http://localhost:5173`, which matches the backend's default
`CORS_ORIGINS`.

> This sandbox had no network access, so the scaffold above was
> hand-written and could not be verified with `npm install` / `npm run
> build` here. Please run both locally before the demo — see §12.

## 9. Building

```bash
npm run build   # tsc -b && vite build
npm run preview # serve the production build locally
```

## 10. Backend integration requirements

- Member 1's backend must be running at `VITE_API_URL` with CORS
  configured to allow the frontend's origin (`CORS_ORIGINS` env var on
  the backend).
- `/ws` must accept connections with no auth (matches the current
  backend implementation).
- No backend changes are required for the endpoints this frontend
  uses — the contract above matches `app/api/routes.py` and
  `app/schemas/responses.py` as found in the uploaded backend.

## 11. Deployment instructions

1. Deploy to Vercel or Netlify (static Vite build).
2. Set `VITE_API_URL` to the deployed backend's HTTPS URL.
3. Set `VITE_WS_URL` to the backend's WebSocket URL using `wss://`
   (required once the dashboard itself is served over HTTPS — mixed
   `ws://` content will be blocked by the browser).
4. Set `VITE_USE_MOCK_DATA=false`.
5. On the backend, add the deployed frontend origin to `CORS_ORIGINS`.

## 12. Verification checklist

- [ ] `npm install` completes without errors
- [ ] `npm run build` completes without TypeScript/ESLint errors
- [ ] Dashboard loads against a local backend (`VITE_USE_MOCK_DATA=false`)
- [ ] Dashboard loads against mock data (`VITE_USE_MOCK_DATA=true`) with no backend running
- [ ] Stats, sources, runs, and records all populate
- [ ] "Run Ingestion" starts a run and the dashboard updates live via WebSocket
- [ ] Stopping the backend shows "DISCONNECTED" + the "Live updates unavailable" banner, and REST data stays visible
- [ ] Empty states render correctly against a freshly reset/empty database
- [ ] Responsive down to a narrow mobile viewport, no horizontal page scroll
- [ ] Deployed build: no CORS errors, no mixed-content errors, WebSocket connects over `wss://`

## 13. Known integration gaps

- `GET /api/runs/{run_id}` is implemented in `api.ts` but not yet
  wired into the UI (e.g. a "view run detail" drill-down) — nothing
  currently calls it.
- The activity feed and pipeline diagram are purely a visualization of
  events the backend already sends; no additional backend work is
  needed to support them.
