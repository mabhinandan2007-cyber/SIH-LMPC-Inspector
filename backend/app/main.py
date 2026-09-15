"""
LMPC Label Scanner API — Application Entry Point.

Creates the FastAPI application instance, configures middleware,
mounts route modules, and initializes the database schema via
a lifespan context manager (instead of top-level side-effects).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import scans
from app.db.database import engine, Base


# ---------------------------------------------------------------------------
# Lifespan: run startup / shutdown tasks without top-level side-effects
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; clean up on shutdown."""
    Base.metadata.create_all(bind=engine)
    yield  # application is running
    # Add any shutdown cleanup here if needed


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="LMPC Label Scanner API",
    description="Automated compliance verification for packaged commodity labels under the Legal Metrology (Packaged Commodities) Rules.",
    version="0.2.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — restrict to known frontend origins in production
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5500",  # VS Code Live Server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Route mounting
# ---------------------------------------------------------------------------
app.include_router(scans.router, prefix="/api/scans", tags=["scans"])


@app.get("/", tags=["health"])
async def read_root() -> dict[str, str]:
    """Health-check endpoint confirming the API is live."""
    return {"message": "LMPC Scanner API is running"}
