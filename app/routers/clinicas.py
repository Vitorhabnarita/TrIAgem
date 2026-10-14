"""
app/routers/clinicas.py — Dados da própria clínica (escopo do token — RN-004).

Não há mais CRUD aberto por id: a clínica é SEMPRE a do usuário autenticado.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ConflitoDeNegocio
from app.models import Clinica, MedicoVeterinario, Sintoma
from app.schemas import ClinicaResumoOut, MedicoCreate, MedicoOut, SintomaOut
from app.security import PAPEL_GESTOR, UsuarioAtual, exigir_papeis, usuario_atual

router = APIRouter(prefix="/clinicas", tags=["Clínica"])


@router.get("/me", response_model=ClinicaResumoOut, summary="Clínica do usuário logado")
async def minha_clinica(
    user: UsuarioAtual = Depends(usuario_atual), db: AsyncSession = Depends(get_db)
) -> Clinica:
    return await db.get(Clinica, user.id_clinica)  # type: ignore[return-value]


@router.get("/me/medicos", response_model=list[MedicoOut], summary="Médicos da clínica")
async def listar_medicos(
    user: UsuarioAtual = Depends(usuario_atual), db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(MedicoVeterinario)
        .where(MedicoVeterinario.id_clinica == user.id_clinica)
        .order_by(MedicoVeterinario.nome)
    )
    return res.scalars().all()


@router.post("/me/medicos", response_model=MedicoOut, status_code=status.HTTP_201_CREATED,
             summary="Cadastrar médico (gestor)")
async def cadastrar_medico(
    payload: MedicoCreate,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> MedicoVeterinario:
    if await db.scalar(
        select(MedicoVeterinario).where(
            MedicoVeterinario.id_clinica == user.id_clinica, MedicoVeterinario.crmv == payload.crmv
        )
    ):
        raise ConflitoDeNegocio(f"CRMV '{payload.crmv}' já está cadastrado nesta clínica.")
    medico = MedicoVeterinario(id_clinica=user.id_clinica, **payload.model_dump())
    db.add(medico)
    await db.flush()
    await db.refresh(medico)
    return medico


@router.get("/me/sintomas", response_model=list[SintomaOut], summary="Catálogo de sintomas ativos")
async def listar_sintomas(
    user: UsuarioAtual = Depends(usuario_atual), db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Sintoma)
        .where(Sintoma.ativo.is_(True))
        .order_by(Sintoma.alerta_urgencia.desc(), Sintoma.categoria, Sintoma.nome_sintoma)
    )
    return res.scalars().all()
