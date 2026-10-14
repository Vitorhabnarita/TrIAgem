"""
app/routers/dashboard.py — Dashboard gerencial B2B (ROI — RN-003). Somente gestor.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import agora_utc, garantir_utc
from app.exceptions import EstadoInvalido
from app.schemas import RoiOut
from app.security import PAPEL_GESTOR, UsuarioAtual, exigir_papeis
from app.services.roi import calcular_roi

router = APIRouter(prefix="/dashboard", tags=["Dashboard B2B"])


@router.get("/roi", response_model=RoiOut, summary="KPIs de ROI da clínica no período")
async def roi(
    de: Optional[datetime] = Query(None, description="Início (ISO 8601). Padrão: 30 dias atrás."),
    ate: Optional[datetime] = Query(None, description="Fim (ISO 8601). Padrão: agora."),
    id_medico: Optional[int] = Query(None, gt=0),
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    fim = garantir_utc(ate) if ate else agora_utc()
    ini = garantir_utc(de) if de else fim - timedelta(days=30)
    if ini >= fim:
        raise EstadoInvalido("O início do período deve ser anterior ao fim.")
    if (fim - ini).days > 366:
        raise EstadoInvalido("Período máximo de 366 dias.")
    return await calcular_roi(db, user.id_clinica, ini, fim, id_medico)

