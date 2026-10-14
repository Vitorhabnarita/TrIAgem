"""
app/routers/clinicas.py — Dados da própria clínica (escopo do token — RN-004).

Não há mais CRUD aberto por id: a clínica é SEMPRE a do usuário autenticado.
"""

import re

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.exceptions import ConflitoDeNegocio
from app.models import Clinica, MedicoVeterinario, Sintoma, Tutor
from app.schemas import (
    ClinicaResumoOut,
    MedicoCreate,
    MedicoOut,
    PetResumoOut,
    SintomaOut,
    TutorComPetsOut,
)
from app.security import (
    PAPEL_GESTOR,
    PAPEL_RECEPCAO,
    UsuarioAtual,
    exigir_papeis,
    usuario_atual,
)

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


@router.get("/me/tutores", response_model=list[TutorComPetsOut],
            summary="Buscar tutores e pets da clínica (agendamento rápido)")
async def buscar_tutores(
    q: str = Query("", max_length=60, description="Parte do nome ou do telefone."),
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_RECEPCAO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Tutor)
        .options(selectinload(Tutor.pets))
        .where(Tutor.id_clinica == user.id_clinica)  # RN-004
        .order_by(Tutor.nome)
        .limit(15)
    )
    termo = q.strip()
    if termo:
        digitos = re.sub(r"\D", "", termo)
        filtros = [Tutor.nome.ilike(f"%{termo}%")]
        if digitos:
            filtros.append(Tutor.telefone.like(f"%{digitos}%"))
        stmt = stmt.where(or_(*filtros))
    tutores = (await db.execute(stmt)).scalars().all()
    return [
        TutorComPetsOut(
            nome=t.nome, telefone=t.telefone,
            pets=[PetResumoOut.model_validate(p) for p in t.pets],
        )
        for t in tutores
    ]
