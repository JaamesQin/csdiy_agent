"""CoursePilot OpenAI-compatible Agent application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.chat_completions import router as chat_router
from app.api.models import router as models_router
from app.protocol.errors import (
    http_exception_handler,
    server_exception_handler,
    validation_exception_handler,
)
from app.storage.database import get_database

@asynccontextmanager
async def lifespan(_: FastAPI):
    get_database().initialize()
    yield


app = FastAPI(
    title="CoursePilot Agent",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, server_exception_handler)
app.include_router(auth_router)
app.include_router(models_router)
app.include_router(chat_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self'; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def chat_page() -> FileResponse:
    # Revalidate the entry point on every navigation: Vite build hashes change
    # atomically, so a cached old index could otherwise reference deleted assets.
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")
