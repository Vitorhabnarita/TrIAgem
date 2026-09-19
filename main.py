"""
main.py — Ponto de entrada da aplicação FastAPI TrIAgem.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicação (startup / shutdown)."""
    # Startup
    yield
    # Shutdown — encerra pool de conexões
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API B2B para triagem veterinária inteligente com IA. "
        "Arquitetura multi-tenant por clínica."
    ),
    lifespan=lifespan,
)


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "healthy"}

