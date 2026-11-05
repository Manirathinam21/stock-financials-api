"""
Stock Financials API — FastAPI application entry point.

Extracts Annual & Quarterly Profit & Loss statements, Balance Sheet, and
Cash Flow statements for Indian (NSE-listed) stocks.

Run with:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
<<<<<<< HEAD
from pathlib import Path
=======
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
<<<<<<< HEAD
from fastapi.staticfiles import StaticFiles
=======
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a

from app.api.routes import router as financials_router
from app.config import settings
from app.core.http_session import aclose_shared_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stock_financials_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("Shutting down — closing shared NSE HTTP session")
    await aclose_shared_client()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Extracts Annual & Quarterly Profit & Loss statements, Balance Sheet, "
        "and Cash Flow for NSE-listed Indian stocks, sourced from NSE's "
        "Corporates Financial Results API and Integrated Filing (iXBRL) API."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error while fetching NSE data."})


<<<<<<< HEAD
=======
@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}


app.include_router(financials_router, prefix="/api/v1", tags=["financials"])
<<<<<<< HEAD

# ---------------------------------------------------------------------------
# Frontend: when the React build exists (Docker/Render), serve it from "/".
# Registered last so /api, /health and /docs take precedence.
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/", tags=["health"])
    async def root():
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}
=======
>>>>>>> 6d4b9288b9d086b7dadd641d3b3121b9bf289a6a
