"""
app/routers/admin.py — Backoffice do TrIAgem (criação de clínicas, médicos e usuários).

Protegido por X-Admin-Key (ADMIN_API_KEY). Nunca exposto ao frontend das clínicas.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ConflitoDeNegocio, RecursoNaoEncontrado
from app.models import Clinica, MedicoVeterinario, Usuario
from app.schemas import (
    ClinicaCreate,
    ClinicaOut,
    MedicoCreate,
    MedicoOut,
    UsuarioCreate,
    UsuarioOut,
)
from app.security import exigir_admin, hash_senha

router = APIRouter(prefix="/admin", tags=["Backoffice"], dependencies=[Depends(exigir_admin)])


async def _clinica_ou_404(db: AsyncSession, id_clinica: int) -> Clinica:
    clinica = await db.get(Clinica, id_clinica)
    if clinica is None:
        raise RecursoNaoEncontrado(f"Clínica {id_clinica} não encontrada.")
    return clinica


@router.post("/clinicas", response_model=ClinicaOut, status_code=status.HTTP_201_CREATED,
             summary="Cadastrar clínica (tenant)")
async def criar_clinica(payload: ClinicaCreate, db: AsyncSession = Depends(get_db)) -> Clinica:
    if await db.scalar(select(Clinica).where(Clinica.cnpj == payload.cnpj)):
        raise ConflitoDeNegocio(f"Já existe uma clínica com o CNPJ {payload.cnpj}.")
    clinica = Clinica(**payload.model_dump())
    db.add(clinica)
    await db.flush()
    await db.refresh(clinica)
    return clinica


@router.post("/clinicas/{id_clinica}/medicos", response_model=MedicoOut,
             status_code=status.HTTP_201_CREATED, summary="Cadastrar médico veterinário na clínica")
async def criar_medico(
    id_clinica: int, payload: MedicoCreate, db: AsyncSession = Depends(get_db)
) -> MedicoVeterinario:
    await _clinica_ou_404(db, id_clinica)
    if await db.scalar(
        select(MedicoVeterinario).where(
            MedicoVeterinario.id_clinica == id_clinica, MedicoVeterinario.crmv == payload.crmv
        )
    ):
        raise ConflitoDeNegocio(f"CRMV '{payload.crmv}' já está cadastrado nesta clínica.")
    medico = MedicoVeterinario(id_clinica=id_clinica, **payload.model_dump())
    db.add(medico)
    await db.flush()
    await db.refresh(medico)
    return medico


@router.post("/clinicas/{id_clinica}/usuarios", response_model=UsuarioOut,
             status_code=status.HTTP_201_CREATED, summary="Criar usuário de acesso da clínica")
async def criar_usuario(
    id_clinica: int, payload: UsuarioCreate, db: AsyncSession = Depends(get_db)
) -> Usuario:
    await _clinica_ou_404(db, id_clinica)
    if await db.scalar(select(Usuario).where(func.lower(Usuario.email) == payload.email.lower())):
        raise ConflitoDeNegocio("Já existe um usuário com este e-mail.")
    if payload.id_medico is not None:
        medico = await db.get(MedicoVeterinario, payload.id_medico)
        if medico is None or medico.id_clinica != id_clinica:
            raise RecursoNaoEncontrado("Médico informado não pertence a esta clínica.")
    usuario = Usuario(
        id_clinica=id_clinica,
        id_medico=payload.id_medico,
        nome=payload.nome,
        email=payload.email.lower(),
        senha_hash=hash_senha(payload.senha),
        papel=payload.papel,
    )
    db.add(usuario)
    await db.flush()
    await db.refresh(usuario)
    return usuario

