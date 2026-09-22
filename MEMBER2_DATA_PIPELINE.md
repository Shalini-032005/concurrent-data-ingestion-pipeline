# Member 2 — Mock Data Sources, Normalization, Validation, Deduplication

This document is the integration guide for the data-processing layer. It
covers the three mock sources, the canonical schema, normalization and
validation rules, the SHA-256 deduplication strategy, and exactly how it
all plugs into Member 1's backend.

## 1. What was built

```
backend/app/
├── sources/
│   ├── __init__.py        # get_real_sources() — mirrors get_demo_sources()
│   ├── exceptions.py      # SourceFetchError
│   ├── source_a.py        # SourceA — id/name/email/amount/created schema
│   ├── source_b.py        # SourceB — customer_id/full_name/email_address/value/timestamp
│   └── source_c.py        # SourceC — userId/username/mail/transaction_value/createdAt
└── ingestion/
    ├── normalizer.py      # RecordNormalizer — maps + cleans + validates
    ├── validator.py       # validate_records() / ValidationResult
    └── deduplicator.py    # RecordDeduplicator — SHA-256 fingerprint dedupe
```

Plus tests: `tests/test_sources.py`, `test_normalizer.py`,
`test_validator.py`, `test_deduplicator.py`, `test_pipeline_integration.py`
(28 new tests; 47 total pass, including Member 1's original 19).

**One line changed in Member 1's code**, exactly where
`MEMBER1_BACKEND.md` says to change it —
`app/services/ingestion_service.py`:
- `get_demo_sources()` → `get_real_sources()`
- `build_orchestrator()` now passes `normalizer=RecordNormalizer()`,
  `deduplicator=RecordDeduplicator()`

Nothing else in `app/api`, `app/core`, `app/repositories`,
`app/ingestion/orchestrator.py`, or `main.py` was touched.

**Design decision:** the brief suggests a canonical model at
`app/schemas/records.py`. Member 1 had already defined
`CanonicalRecord` in `app/schemas/responses.py` and wired the entire
backend (routes, repository, orchestrator) around it. Rather than create
a second, competing canonical model, `RecordNormalizer` builds and
returns Member 1's existing `CanonicalRecord` — the "smallest compatible
change" the brief asks for when a conflict like this comes up.

## 2. Source schemas

**Source A** — `app/sources/source_a.py`
```json
{"id": "A-001", "name": "Alice", "email": "ALICE@EXAMPLE.COM", "amount": "1500", "created": "22-09-2026"}
```

**Source B** — `app/sources/source_b.py`
```json
{"customer_id": "A-001", "full_name": " Alice ", "email_address": "alice@example.com", "value": 1500, "timestamp": "2026-09-22T10:30:00"}
```

**Source C** — `app/sources/source_c.py`
```json
{"userId": "A-001", "username": "Alice", "mail": "alice@example.com", "transaction_value": 1500, "createdAt": "2026-09-22T10:30:00"}
```

Each source satisfies the `IngestionSource` contract exactly
(`name: str`, `async def fetch(self) -> list[dict]`) — `fetch()` also
accepts an optional `simulate_failure: bool = False` keyword for direct
unit testing of the source in isolation; the orchestrator never needs to
pass it (its own `simulate_failure` mechanism works at the run level,
outside any source's knowledge).

## 3. Async behavior

All three sources use `await asyncio.sleep(...)`, never `time.sleep()`.
Delays: Source A = 1.0s, Source B = 1.5s, Source C = 0.8s — matching
Member 1's documented concurrency proof (sequential ≈ 3.3s, concurrent ≈
max(1.0, 1.5, 0.8) ≈ 1.5s). Verified live: a real `/api/ingest` run
completes in ~1502ms.

## 4. Intentional duplicates (fixed, deterministic dataset)

Source A has 10 well-formed records (`A-001`..`A-010`) plus **one
intentionally invalid record** (`A-011`: malformed email + negative
value) so validation has something real to reject in a live demo, not
just in tests.

| Overlap | Appears in |
|---|---|
| `A-001` | Source A, Source B, Source C |
| `A-002`, `A-003`, `A-004` | Source A + one of B/C |
| `A-005` | Source A + Source C |
| `B-001`, `B-002` | Source B + Source C |

Resulting math for the full fixed dataset (asserted in
`tests/test_pipeline_integration.py`, and confirmed against a live run):

| Metric | Value |
|---|---|
| Raw records received (A+B+C) | 31 |
| Rejected by validation | 1 |
| Valid, normalized records | 30 |
| Unique after dedup | 22 |
| Duplicates removed | 8 |

## 5. Canonical schema

Reusing `app/schemas/responses.py::CanonicalRecord`:
```python
record_id: str
name: str | None
email: str | None
value: float | None
source: str
created_at: str | None
ingested_at: str  # auto-filled
```
`RecordDeduplicator` additionally attaches `record_hash: str` to every
record it processes (the model allows extra fields), so Member 3 can
persist it directly.

## 6. Normalization rules (`app/ingestion/normalizer.py`)

| Rule | Behavior |
|---|---|
| Name | `strip()` |
| Email | `strip().lower()` |
| Value | coerced to `float` (handles `"1500"`, `1500`, `"1500.50"`); unconvertible → `None` (caught by validation, never crashes) |
| Record ID | `strip()`, logical value preserved |
| Timestamp | Source A's `DD-MM-YYYY` and Source B/C's ISO-8601 both parsed into one consistent timezone-aware (UTC) ISO-8601 string; unparsable → `None` |

**Schema detection:** because the orchestrator flattens all sources'
raw records into one list before normalization, each raw dict is matched
to its schema (and therefore its source name) by which field names are
present on it — `id` → Source A, `customer_id` → Source B, `userId` →
Source C. The three schemas share no field names, so this is
unambiguous.

## 7. Validation rules (`app/ingestion/validator.py`)

Runs on already-normalized `CanonicalRecord`s (normalize → validate →
dedupe, per the required pipeline order). Rejects (never raises) on:
missing `record_id`, missing `name`, missing/malformed `email`,
non-numeric `value`, negative `value`, or an unparsable `created_at`.
Each rejected record gets `{"record_id", "source", "errors": [...]}`
with plain-English reasons — never a Python stack trace.

## 8. SHA-256 fingerprint strategy (`app/ingestion/deduplicator.py`)

```python
fingerprint = sha256(f"{record_id.strip().lower()}|{email.strip().lower()}")
```
Deterministic and reproducible: the same logical record (same id +
email) always hashes the same, regardless of which source it came from
or how its whitespace/casing looked before normalization. First
occurrence (in source order A→B→C) wins; later occurrences are counted
as duplicates and dropped. `RecordDeduplicator.last_duplicates` holds
`{"record_hash", "original_source", "duplicate_source", "record_id"}`
for each dropped duplicate, for demo/debugging.

## 9. Integration instructions for Member 1

Already wired — `IngestionService.build_orchestrator()` passes
`normalizer=RecordNormalizer()` and `deduplicator=RecordDeduplicator()`,
and `IngestionService.execute_run()` calls `get_real_sources()` instead
of `get_demo_sources()`. No further changes needed. `demo_sources.py`
was left in place (untouched, unused) in case it's useful for
lightweight local testing without the full dataset.

## 10. Integration instructions for Member 3

Every unique record coming out of `RecordDeduplicator.process()` has:
`record_id, name, email, value, source, created_at, ingested_at, record_hash`
— ready to pass straight into `Repository.save_records()`. No changes
needed on Member 2's side once `PostgresRepository` is implemented; it's
swapped in at `app/services/dependencies.py` per Member 1's contract.

## 11. Test commands

```bash
cd backend
pip install -r requirements.txt --break-system-packages
python3 -m pytest -v
```
47 passed (19 from Member 1 + 28 new): sources (async, schema, counts,
cross-source duplicates, concurrency, failure simulation), normalization
(per-schema mapping + cleaning rules), validation (each rejection rule),
deduplication (counts, fingerprint determinism, cross-source metadata),
and a full end-to-end integration test asserting the exact
31 → 30 → 22 numbers above.
