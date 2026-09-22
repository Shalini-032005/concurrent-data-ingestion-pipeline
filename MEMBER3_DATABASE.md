# Member 3 — Database + Persistence + Statistics

This document covers the PostgreSQL layer: schema, repository API,
environment setup, tests, and how it plugs into Member 1, Member 2, and
Member 4's work.

## Architecture

```
Member 1 Orchestrator (app/ingestion/orchestrator.py)
        │  calls the Repository Protocol only
        ▼
Member 3 Repository  (app/repositories/postgres.py :: PostgresRepository)
        │  SQLAlchemy 2.x async + asyncpg
        ▼
PostgreSQL (local or Supabase)
```

Nothing in `routes.py`, `orchestrator.py`, or `ingestion_service.py` talks
to SQLAlchemy directly. They all depend on the `Repository` **Protocol**
defined in `app/repositories/base.py`. `PostgresRepository` is one
implementation of that protocol; `InMemoryRepository` (Member 1's original
stub) is the other, kept as an automatic fallback when `DATABASE_URL`
isn't set.

## Files added/changed

```
backend/app/database/
├── __init__.py
├── database.py      # async engine, session factory, init_db, health check
└── models.py         # RecordORM, SourceORM, IngestionRunORM

backend/app/repositories/
└── postgres.py        # PostgresRepository — implements Repository protocol

backend/tests/
└── test_database.py   # live-Postgres repository tests (Phases 25-30)

backend/app/services/dependencies.py   # edited: wires in PostgresRepository
backend/main.py                        # edited: init_db() + health check on startup
.env.example                           # edited: documents TEST_DATABASE_URL
```

No existing files were rewritten wholesale — `dependencies.py` and
`main.py` got small, additive edits exactly where their own comments said
Member 3's wiring should go.

## Schema

### `records`

| column            | type                     | notes                          |
|-------------------|--------------------------|---------------------------------|
| id                | Integer PK, autoincrement|                                  |
| record_hash       | String(64), **UNIQUE**   | SHA-256 from Member 2's dedup   |
| source            | String(100)              | indexed                         |
| source_record_id  | String(255), nullable    | original `record_id`; indexed   |
| name              | String(255), nullable    |                                  |
| email             | String(255), nullable    |                                  |
| value             | Float, nullable          |                                  |
| created_at        | DateTime(tz), nullable   | from source; indexed            |
| ingested_at       | DateTime(tz)             | indexed                         |

`record_hash` is UNIQUE and every insert goes through
`INSERT ... ON CONFLICT (record_hash) DO NOTHING` — a second, database-level
duplicate guard behind Member 2's application-level deduplication.

### `sources`

| column             | type                    | notes                              |
|--------------------|-------------------------|--------------------------------------|
| id                 | Integer PK              |                                     |
| source_name        | String(100), **UNIQUE** |                                     |
| status             | String(20)              | HEALTHY / DEGRADED / DOWN / UNKNOWN |
| last_success       | DateTime(tz), nullable  |                                     |
| last_failure       | DateTime(tz), nullable  |                                     |
| records_received   | Integer, default 0      |                                     |
| records_processed  | Integer, default 0      |                                     |
| duplicates         | Integer, default 0      | not yet populated — see note below |
| error_message      | Text, nullable          | not yet populated — see note below |
| updated_at         | DateTime(tz)            | auto-updated on every upsert       |

One row per source, upserted via `ON CONFLICT (source_name) DO UPDATE`
after every run — not one row per run.

> **Note:** Member 1's current `SourceStatus` schema
> (`app/schemas/responses.py`) doesn't carry `duplicates` or
> `error_message` yet, so those two columns exist and default to
> `0`/`NULL` but aren't populated by `update_source_status()` today. If
> `SourceStatus` grows those fields later, `PostgresRepository` picks them
> up automatically (it reads them with `getattr(..., default)`), no
> repository change needed.

### `ingestion_runs`

| column            | type                    | notes                                    |
|-------------------|-------------------------|-------------------------------------------|
| id                | Integer PK, **not** autoincrement | = orchestrator's `run_id`        |
| started_at        | DateTime(tz)            | indexed                                   |
| completed_at      | DateTime(tz), nullable  |                                            |
| duration_ms       | Float, nullable         |                                            |
| status            | String(20)              | RUNNING / COMPLETED / PARTIAL / FAILED; indexed |
| total_received    | Integer, default 0      |                                            |
| total_processed   | Integer, default 0      |                                            |
| total_duplicates  | Integer, default 0      |                                            |
| total_failed      | Integer, default 0      |                                            |
| failed_sources    | JSON, nullable          | list of source names that didn't succeed  |
| source_results    | JSON, nullable          | full per-source breakdown (see below)     |

`id` is **not** autoincrement — the orchestrator generates `run_id` itself
(`app/ingestion/orchestrator.py::next_run_id()`) and calls
`save_ingestion_run()` exactly once per run with the final summary, so
persistence is a single `INSERT ... ON CONFLICT (id) DO UPDATE`, not a
separate create-then-update pair. `source_results` stores each
`SourceResult` as JSON so `GET /api/runs/{run_id}` can return the complete
`IngestionRunSummary` (Member 4 needs `source_results` too) straight from
one row.

### Indexes

`records.record_hash` and `sources.source_name` get an index automatically
from their `UNIQUE` constraint. Explicitly added beyond that:
`records.source`, `records.source_record_id`, `records.created_at`,
`records.ingested_at`, `ingestion_runs.started_at`, `ingestion_runs.status`
— these are exactly the columns `get_records()`/filtering/ordering and
`get_stats()` actually query on; nothing is indexed speculatively.

## Repository API

`PostgresRepository` (in `app/repositories/postgres.py`) implements every
method of the `Repository` Protocol in `app/repositories/base.py`:

```python
await repository.save_records(records)            # List[CanonicalRecord]
await repository.save_ingestion_run(run)           # IngestionRunSummary (upsert by run_id)
await repository.update_source_status(status)      # SourceStatus (upsert by source name)
await repository.get_stats() -> StatsResponse
await repository.get_sources() -> List[SourceStatus]
await repository.get_records(page=1, page_size=20, source=None) -> {"page", "page_size", "total", "records"}
await repository.get_runs() -> List[IngestionRunSummary]        # newest first, latest 20
await repository.get_run(run_id) -> Optional[IngestionRunSummary]
```

Every method opens its own short-lived `AsyncSession` from an injected
`async_sessionmaker` — the repository is a single shared instance across
concurrent requests, so it never holds one session open across calls.
Persistence failures are logged with full detail server-side and re-raised
as `DatabaseError` (never a raw `SQLAlchemyError`/`asyncpg` exception) —
the repository itself never raises `HTTPException`; that conversion is
Member 1's API layer's job.

## Environment configuration

Everything is driven by one variable:

```
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/database
```

- Never hardcode credentials — `.env` for local dev, real env vars in
  deployment, neither committed.
- `postgres://...` and plain `postgresql://...` URLs (e.g. copy-pasted
  straight from Supabase or Heroku) are automatically normalized to
  `postgresql+asyncpg://...` — you don't need to hand-edit the URL Supabase
  gives you.
- If `DATABASE_URL` is empty, the app **still runs**, using the original
  `InMemoryRepository` — Postgres is opt-in, not required to demo the rest
  of the pipeline.

### Local PostgreSQL setup

```bash
# with Docker
docker run --name ingestion-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ingestion_db -p 5432:5432 -d postgres:16

# .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion_db
```

Tables are created automatically on startup (`init_db()` runs
`Base.metadata.create_all()` — no Alembic, per the hackathon-appropriate
"reliable, simple, deployable" priority). No manual migration step needed.

### Supabase setup

1. Create a Supabase project.
2. Project Settings → Database → Connection string. Two options:
   - **Direct connection** (port 5432) — fine for the hackathon's traffic
     level.
   - **Pooler / pgbouncer** (port 6543) — needed if you expect many
     concurrent connections.
3. Copy the connection string into `DATABASE_URL` in `.env`. Either
   `postgres://` or `postgresql://` form works — it's normalized
   automatically.
4. The Supabase pooler runs in transaction mode, which doesn't support
   asyncpg's server-side prepared-statement cache. `get_engine()` always
   passes `statement_cache_size=0` to asyncpg, so this works against
   **both** the direct connection and the pooler without any
   Supabase-specific code path or config flag.
5. Start the app — `init_db()` creates the three tables on Supabase exactly
   as it would locally. No Supabase-only SQL or extensions are used
   anywhere.

### Running tests

```bash
# separate, disposable database — never your Supabase/production one
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion_test
pytest backend/tests/test_database.py -v
```

If `TEST_DATABASE_URL` isn't set, or that database isn't reachable, every
test in `test_database.py` is **skipped** (not failed) — so `pytest` stays
green on a fresh clone before Postgres is set up. Each test gets a
drop-all/create-all cycle for a clean slate; tables are dropped again at
teardown.

Covers: connection check, table creation, record insert, unique
`record_hash` (both across separate `save_records()` calls and within one
batch), duplicate insert doesn't crash, ingestion run create + upsert,
run-not-found, run retrieval ordering, source upsert (create then update
in place), source retrieval, statistics computed from real stored values
(not just response shape), record pagination (25 records / page_size 10 →
10/10/5), and source filtering.

## Integration with Member 1

Nothing to change in `routes.py`, `orchestrator.py`, or
`ingestion_service.py` — they already depend on the `Repository` Protocol.
The only wiring point, `app/services/dependencies.py`, now does:

```python
if settings.DATABASE_URL:
    _repository = PostgresRepository(get_session_factory(settings.DATABASE_URL))
else:
    _repository = InMemoryRepository()
```

`main.py`'s `lifespan()` now also calls `init_db()` and
`check_database_connection()` on startup when `DATABASE_URL` is set (both
guarded by `try/except` — a missing/unreachable database never prevents
the API itself from starting; it just keeps using the in-memory
repository). `app/database/database.py::check_database_connection()` is
available if you want to surface DB health from `GET /health` — not wired
into that route today, to avoid touching it without you looking it over
first.

Required environment variable: `DATABASE_URL` (see above). Nothing else.

## Integration with Member 2

Member 2's `RecordDeduplicator` (`app/ingestion/deduplicator.py`) already
attaches `record_hash` directly onto each `CanonicalRecord` before the
orchestrator calls `repository.save_records(...)` — the exact field name
the `records` table's UNIQUE constraint is keyed on. No conversion step
was needed; `PostgresRepository._record_to_row()` reads
`record.record_hash` straight off the Pydantic model (it's an
`extra="allow"` field, so this works without a schema change).

## Expected data structures for Member 4

Straight from `get_stats()` / `get_sources()` / `get_records()` /
`get_runs()` / `get_run()`, matching Member 1's existing
`app/schemas/responses.py` shapes exactly (no new shapes introduced):

```jsonc
// GET /api/stats
{
  "total_received": 100, "total_processed": 82, "total_duplicates": 15,
  "total_failed": 3, "last_run_status": "COMPLETED",
  "last_run_timestamp": "2026-09-22T10:30:00+00:00", "last_run_duration_ms": 1502.3
}

// GET /api/sources
[{ "source": "Source A", "status": "HEALTHY", "last_success": "...",
   "last_failure": null, "records_received": 10, "records_processed": 9 }]

// GET /api/records?page=1&page_size=20&source=Source%20A
{ "page": 1, "page_size": 20, "total": 100, "records": [
  { "record_id": "A-001", "name": "Alice", "email": "alice@example.com",
    "value": 1500.0, "source": "Source A", "created_at": "...",
    "ingested_at": "...", "record_hash": "..." } ] }

// GET /api/runs
[{ "run_id": 10, "status": "COMPLETED", "started_at": "...", "completed_at": "...",
   "duration_ms": 1512.0, "total_received": 30, "total_processed": 24,
   "total_duplicates": 6, "total_failed": 0, "source_results": [ ... ] }]

// GET /api/runs/{run_id} -> same shape as one item above, or 404
```

No changes required from any other teammate for this to work — all of it
flows through interfaces they already coded against.
