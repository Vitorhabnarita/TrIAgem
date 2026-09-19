"""
main.py — Ponto de entrada da aplicação FastAPI TrIAgem.

Fluxo de negócio:
  Recepção agenda consulta → Link WhatsApp para tutor → Tutor preenche
  triagem mobile → IA processa → Veterinário lê relatório pré-consulta.

Regra de Ouro: economia de 15 min por consulta, comprovada via timestamps.
Regra Ética: o sistema NUNCA emite diagnóstico, apenas suporte à decisão.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.routers import clinicas, consultas, triagem


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicação (startup / shutdown)."""
    yield
    # Shutdown — encerra pool de conexões graciosamente
    from app.database import engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Instância FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "**TrIAgem** — SaaS B2B de triagem veterinária inteligente.\n\n"
        "Fluxo: `Agendamento → Triagem Digital (Tutor) → IA → Relatório (Veterinário)`\n\n"
        "> ⚠️ **Regra Ética**: Este sistema **nunca emite diagnósticos**. "
        "Toda análise de IA é de suporte à decisão clínica."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Em produção: restringir para domínios da clínica
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Handlers de exceção de domínio
# ---------------------------------------------------------------------------

register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(clinicas.router)
app.include_router(consultas.router)
app.include_router(triagem.router)

# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"], summary="Status da API")
async def root() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict:
    """Verifica se a API está respondendo. Usado por load balancers e monitoramento."""
    return {"status": "healthy"}
