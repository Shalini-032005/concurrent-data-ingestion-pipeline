"""
FastAPI application entrypoint — Member 1 (Backend + Concurrency).

Local run:
    cd backend
    uvicorn main:app --reload

Deployment (e.g. Render):
    uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.routes import router as api_router
from app.api.websocket import websocket_endpoint
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.database import check_database_connection, dispose_engine, init_db

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started (environment=%s)", settings.ENVIRONMENT)
    logger.info("CORS origins: %s", allowed_origins)
    logger.info(
        "Ingestion config: timeout=%.1fs max_retries=%d retry_delay=%.2fs",
        settings.INGESTION_TIMEOUT, settings.MAX_RETRIES, settings.RETRY_DELAY,
    )
    # --- Database (Member 3) ---
    # Falls back to the in-memory repository (app/services/dependencies.py)
    # when DATABASE_URL isn't set, so a missing/unreachable database never
    # prevents the API itself from starting.
    if settings.DATABASE_URL:
        try:
            await init_db(settings.DATABASE_URL)
            healthy = await check_database_connection(settings.DATABASE_URL)
            logger.info("Database connection: %s", "OK" if healthy else "FAILED")
        except Exception:  # noqa: BLE001
            logger.exception("Database initialization failed; continuing without persistent storage")
    else:
        logger.info("DATABASE_URL not set; using in-memory repository")

    yield

    if settings.DATABASE_URL:
        await dispose_engine(settings.DATABASE_URL)
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend for the Concurrent Data Ingestion Pipeline hackathon project. "
        "Handles async multi-source ingestion, REST APIs, and real-time "
        "WebSocket updates."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS ---
# Development allows localhost:5173 by default (see .env.example). In
# production, set CORS_ORIGINS to the deployed frontend's origin(s) —
# never leave this as "*" in production.
allowed_origins = settings.cors_origins_list or ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(api_router)
app.add_api_websocket_route("/ws", websocket_endpoint)
