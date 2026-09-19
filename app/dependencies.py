"""
app/dependencies.py — Dependências reutilizáveis para injeção via FastAPI.

Centraliza helpers de consulta ao banco, reduzindo boilerplate nos routers
e garantindo respostas de erro consistentes.
"""

from typing import TypeVar

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import RecursoNaoEncontrado
from app.models import Base

# Alias para tipagem genérica
ModelType = TypeVar("ModelType", bound=Base)


# ---------------------------------------------------------------------------
# get_or_404 — busca por PK e levanta 404 se não encontrar
# ---------------------------------------------------------------------------

async def get_or_404(
    model: type[ModelType],
    pk: int,
    session: AsyncSession,
    detail: str | None = None,
) -> ModelType:
    """
    Busca um registro por chave primária. Levanta RecursoNaoEncontrado (404)
    se não existir.

    Uso:
        clinica = await get_or_404(Clinica, id_clinica, db)
    """
    result = await session.get(model, pk)
    if result is None:
        nome = model.__tablename__
        raise RecursoNaoEncontrado(
            detail=detail or f"{nome} com id={pk} não encontrado."
        )
    return result  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Re-exporta get_db para uso direto nos routers sem import extra
# ---------------------------------------------------------------------------

DBSession = Depends(get_db)
