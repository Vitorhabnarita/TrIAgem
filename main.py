"""
main.py — Ponto de entrada da aplicação FastAPI TrIAgem.

Fluxo: Recepção agenda → link único (WhatsApp) → Tutor preenche a Triagem Pré-Consulta →
IA gera o Relatório Clínico Prévio → médico lê o Briefing Estruturado de Triagem antes do paciente
entrar → cronômetro em UTC comprova o ROI.

Regra de Ouro: economia de 15 a 20 min por consulta, comprovada por timestamps UTC.
Regra Ética: o sistema NUNCA emite diagnóstico, apenas suporte à decisão.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.exceptions import register_exception_handlers
from app.routers import admin, auth, clinicas, consultas, dashboard, publico, triagem

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()   # encerra o pool de conexões graciosamente


_producao = settings.ambiente.lower() == "producao"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**TrIAgem** — Triagem Pré-Consulta assistida por IA para clínicas e hospitais.\n\n"
        "Fluxo: `Agendamento → Triagem Pré-Consulta (Tutor) → Relatório Clínico Prévio (IA) → "
        "Briefing Estruturado (Profissional)`\n\n"
        "> ⚠️ **Regra Ética**: este sistema **nunca emite diagnósticos**. "
        "Toda análise de IA é de suporte à decisão clínica."
    ),
    lifespan=lifespan,
    docs_url=None if _producao else "/docs",
    redoc_url=None if _producao else "/redoc",
    openapi_url=None if _producao else "/openapi.json",
)

# CORS restrito às origens configuradas (nunca "*" com credenciais)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,   # autenticação por Bearer token, não por cookie
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"],
)


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next) -> Response:
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")   # dados de saúde: nada em cache
    return resp


register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(clinicas.router)
app.include_router(consultas.router)
app.include_router(triagem.router)
app.include_router(publico.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"], summary="Status da API")
async def root() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/health", tags=["Health"], summary="Health check (inclui banco de dados)")
async def health_check(response: Response) -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        response.status_code = 503
        return {"status": "degraded", "database": "indisponivel"}
    return {"status": "healthy", "database": "ok"}
