# Member 1 — Backend + Concurrency + API + WebSocket

This document is the integration guide for Members 2, 3, and 4. It
describes what's built, how to run it, and exactly what contract to code
against so everyone's work plugs together without merge conflicts.

## 1. Backend structure

```
backend/
├── main.py                        # FastAPI app, CORS, lifespan, router wiring
├── requirements.txt
├── pytest.ini
├── app/
│   ├── api/
│   │   ├── routes.py               # All REST endpoints (thin — calls services)
│   │   ├── websocket.py            # ConnectionManager + /ws endpoint
│   │   └── error_handlers.py       # Global exception -> clean JSON
│   ├── core/
│   │   ├── config.py                # Settings (env vars), get_settings()
│   │   └── logging_config.py        # configure_logging(), mask_secret()
│   ├── ingestion/
│   │   ├── interfaces.py            # Source / Normalizer / Deduplicator Protocols
│   │   ├── orchestrator.py          # THE concurrent ingestion engine
│   │   ├── retry.py                 # retry_async() helper
│   │   ├── events.py                # EventBroadcaster Protocol
│   │   └── demo_sources.py          # TEMPORARY mock sources (Member 2 replaces)
│   ├── repositories/
│   │   └── base.py                  # Repository Protocol + InMemoryRepository (TEMP)
│   ├── schemas/
│   │   └── responses.py             # All Pydantic models (single source of truth)
│   └── services/
│       ├── dependencies.py          # Shared singletons / DI wiring
│       ├── ingestion_service.py     # Route -> orchestrator glue
│       └── stats_service.py         # Route -> repository reads glue
└── tests/
    ├── test_api.py
    ├── test_orchestrator.py
    └── test_websocket.py
```

## 2. How to start the backend

```bash
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
cp ../.env.example ../.env   # optional — defaults work without it
uvicorn main:app --reload
```

Visit:
- http://localhost:8000/docs — interactive Swagger UI
- http://localhost:8000/health — health check
- ws://localhost:8000/ws — WebSocket

For deployment (Render or similar):

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Run tests:

```bash
cd backend
python3 -m pytest -v
```

19/19 tests currently pass, including a timing-based proof that sources
run concurrently (not sequentially).

## 3. API endpoints

| Method | Path                | Purpose                                           |
|--------|---------------------|----------------------------------------------------|
| GET    | `/`                  | Root/status message                                |
| GET    | `/health`            | Health check (used by deploy platforms too)        |
| POST   | `/api/ingest`        | Start a concurrent ingestion run (non-blocking)    |
| GET    | `/api/stats`         | Aggregated stats across all runs                   |
| GET    | `/api/sources`       | Latest health/status per source                    |
| GET    | `/api/records`       | Paginated records, optional `?source=` filter      |
| GET    | `/api/runs`          | All previous ingestion runs                        |
| GET    | `/api/runs/{run_id}` | One specific run                                   |

`POST /api/ingest` accepts an optional query param `?simulate_failure=Source%20B`
for demo purposes — it force-fails the named source so you can show the
dashboard handling a partial failure live. It's clearly a dev/demo-only
mechanism (see `app/api/routes.py`), not a real feature to build UI around.

`POST /api/ingest` returns immediately:
```json
{ "run_id": 1, "status": "RUNNING" }
```
The actual ingestion runs in a FastAPI `BackgroundTask`. Poll
`GET /api/runs/{run_id}` or listen on the WebSocket for live progress and
the final result.

## 4. WebSocket

Connect to `ws://<host>/ws`. No auth. You'll receive JSON messages shaped
like this as an ingestion run progresses:

```json
{"event": "INGESTION_STARTED", "run_id": 1, "timestamp": "..."}
{"event": "SOURCE_STARTED", "run_id": 1, "source": "Source A", "timestamp": "..."}
{"event": "SOURCE_COMPLETED", "run_id": 1, "source": "Source A", "records": 10, "duration_ms": 1001.0, "timestamp": "..."}
{"event": "SOURCE_FAILED", "run_id": 1, "source": "Source B", "error": "Timed out after 5.0s", "duration_ms": 5000.2, "timestamp": "..."}
{"event": "INGESTION_COMPLETED", "run_id": 1, "status": "PARTIAL", "duration_ms": 1502.9, "timestamp": "..."}
```

Fields that don't apply to a given event type are simply omitted (not
sent as `null`). The event `status` values are: `SUCCESS`, `FAILED`,
`TIMEOUT` for sources, and `COMPLETED` / `PARTIAL` / `FAILED` for the
overall run.

## 5. Integration contracts (READ THIS — Members 2 & 3)

The backend never imports concrete implementations from Member 2 or 3
directly — everything is a Python `Protocol` (structural typing, no
inheritance needed). Just write a class with matching method signatures.

### Source contract (Member 2)

```python
class MySource:
    name: str = "Source A"

    async def fetch(self) -> list[dict]:
        # raise an exception on failure — don't return an error shape
        ...
```

Wire your real sources in by editing `get_demo_sources()` in
`app/ingestion/demo_sources.py`, or better, add your own
`app/ingestion/real_sources.py` and swap the import in
`app/services/ingestion_service.py::IngestionService.execute_run` (one line).

### Normalizer contract (Member 2)

```python
class MyNormalizer:
    def normalize(self, records: list[dict]) -> list[CanonicalRecord]:
        ...
```

Target shape (`app/schemas/responses.py::CanonicalRecord`):
```python
record_id: str
name: str | None
email: str | None
value: float | None
source: str
created_at: str | None
ingested_at: str  # auto-filled if omitted
```
Extra fields are allowed (`model_config = ConfigDict(extra="allow")`).

Wire it in via `IngestionOrchestrator(normalizer=MyNormalizer(), ...)` in
`app/services/ingestion_service.py::IngestionService.build_orchestrator`.

### Deduplicator contract (Member 2)

```python
class MyDeduplicator:
    def process(self, records: list[CanonicalRecord]) -> tuple[list[CanonicalRecord], int]:
        # returns (unique_records, duplicate_count)
        ...
```
Wire it in the same place as the normalizer, via `deduplicator=...`.

### Database / repository contract (Member 3)

Implement `app/repositories/base.py::Repository`:

```python
async def save_records(records: list[CanonicalRecord]) -> None
async def save_ingestion_run(run: IngestionRunSummary) -> None
async def update_source_status(status: SourceStatus) -> None
async def get_stats() -> StatsResponse
async def get_sources() -> list[SourceStatus]
async def get_records(page=1, page_size=20, source=None) -> dict
async def get_runs() -> list[IngestionRunSummary]
async def get_run(run_id: int) -> IngestionRunSummary | None
```

An `InMemoryRepository` TEMPORARY implementation already satisfies this
and is used by default — the whole API is testable today without
Postgres. To go live: build `app/repositories/postgres.py::PostgresRepository`
using SQLAlchemy (async engine) + `asyncpg`, backed by `DATABASE_URL`, then
swap the single line in `app/services/dependencies.py`:

```python
_repository: Repository = PostgresRepository(settings.DATABASE_URL)
```

Nothing else changes — routes, services, and the orchestrator all depend
on the `Repository` Protocol, never on SQLAlchemy internals.

### Event contract (used internally, FYI for Member 4)

```python
async def broadcast(event: IngestionEvent) -> None
```
`ConnectionManager` in `app/api/websocket.py` already implements this and
is wired into the orchestrator by default. Member 4 just needs to consume
the JSON messages described in section 4 — no action needed here.

## 6. Environment variables

| Variable            | Default                    | Notes                                      |
|----------------------|----------------------------|---------------------------------------------|
| `DATABASE_URL`       | `""`                        | Owned by Member 3's Postgres implementation |
| `CORS_ORIGINS`       | `http://localhost:5173`     | Comma-separated list for production         |
| `ENVIRONMENT`        | `development`               | `development` \| `production`               |
| `INGESTION_TIMEOUT`  | `5` (seconds)                | Per-source timeout                          |
| `MAX_RETRIES`        | `3`                          | Attempts per source, including the first    |
| `RETRY_DELAY`        | `0.5` (seconds)              | Delay between retry attempts                |
| `PORT`               | `8000`                       | Used in deployment start command            |

See `.env.example` at the repo root.

## 7. How each teammate should integrate

**Member 2 (sources, validation, normalization, dedup):**
1. Implement classes matching the Source / Normalizer / Deduplicator
   contracts above.
2. Replace `get_demo_sources()` usage and wire your normalizer/deduplicator
   into `IngestionService.build_orchestrator()` — that's the only file
   you should need to touch in the backend.
3. Validation can happen inside your `fetch()` (raise on invalid data) or
   as a step before/inside your normalizer — your call.

**Member 3 (PostgreSQL):**
1. Implement `PostgresRepository` satisfying the `Repository` Protocol.
2. Swap it into `app/services/dependencies.py::_repository`.
3. Everything else (routes, orchestrator, stats service) keeps working
   unmodified.

**Member 4 (React dashboard):**
1. REST base URL: `http://localhost:8000` (dev) — CORS is already open
   for `http://localhost:5173`.
2. Connect to `ws://localhost:8000/ws` for live events (section 4).
3. Call `POST /api/ingest` to trigger a run, then either poll
   `GET /api/runs/{run_id}` or just watch the WebSocket for
   `INGESTION_COMPLETED`.
4. Use `GET /api/stats`, `/api/sources`, `/api/records`, `/api/runs` to
   populate the dashboard views.
5. For the "one source fails" demo, call
   `POST /api/ingest?simulate_failure=Source%20B`.

## 8. Tests performed

```
19 passed in ~4.5s
```
Covering: app startup, all REST endpoints (including 404 error shape),
WebSocket connect/disconnect, WebSocket broadcast + broken-client
handling, and — most importantly — the orchestrator's concurrency,
timeout, retry (bounded, and recovering from transient failure), one
source's failure not blocking others, `simulate_failure` behavior, event
ordering, repository persistence, and that duration is measured (not
hardcoded).

Manually verified against a live `uvicorn` server (see section 2):
`GET /`, `/health`, `/docs`, `/openapi.json`, `POST /api/ingest`,
`GET /api/stats`, `/api/sources`, `/api/records`, `/api/runs`,
`/api/runs/{id}`, and the `/ws` WebSocket live event stream.

Concurrency proof from a real run (demo sources A=1.0s, B=1.5s, C=0.8s):
total run duration was **~1502ms**, matching the slowest source — not
the sequential sum of ~3300ms.

## 9. What's NOT included (by design)

- Real mock sources with validation rules → Member 2
- Real normalization mapping logic → Member 2
- Real deduplication algorithm → Member 2
- SQLAlchemy models / PostgreSQL persistence → Member 3
- React dashboard / charts → Member 4

Everything above has a clean seam (`Protocol` + one wiring point) so
those can be dropped in independently without backend changes.
