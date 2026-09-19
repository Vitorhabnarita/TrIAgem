"""
app/routers/clinicas.py — Endpoints administrativos de clínicas e médicos.

Audiência: equipe interna / backoffice do TrIAgem.
Futuramente protegidos por autenticação de admin (JWT/API-key).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_or_404
from app.exceptions import ConflitoDeNegocio
from app.models import Clinica, MedicoVeterinario
from app.schemas import (
    ClinicaCreate,
    ClinicaOut,
    ClinicaUpdate,
    MedicoVeterinarioCreate,
    MedicoVeterinarioOut,
)

router = APIRouter(prefix="/clinicas", tags=["Clínicas"])


# ===========================================================================
# CLÍNICAS
# ===========================================================================

@router.post(
    "",
    response_model=ClinicaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova clínica",
)
async def criar_clinica(
    payload: ClinicaCreate,
    db: AsyncSession = Depends(get_db),
) -> ClinicaOut:
    """
    Cadastra uma nova clínica (tenant) no sistema.
    CNPJ deve ser único globalmente.
    """
    # Verifica CNPJ duplicado com mensagem amigável
    existente = await db.scalar(
        select(Clinica).where(Clinica.cnpj == payload.cnpj)
    )
    if existente:
        raise ConflitoDeNegocio(
            f"Já existe uma clínica cadastrada com o CNPJ {payload.cnpj}."
        )

    clinica = Clinica(**payload.model_dump())
    db.add(clinica)
    await db.flush()   # Popula o id antes do commit
    await db.refresh(clinica)
    return clinica  # type: ignore[return-value]


@router.get(
    "/{id_clinica}",
    response_model=ClinicaOut,
    summary="Buscar clínica por ID",
)
async def buscar_clinica(
    id_clinica: int,
    db: AsyncSession = Depends(get_db),
) -> ClinicaOut:
    return await get_or_404(Clinica, id_clinica, db)  # type: ignore[return-value]


@router.patch(
    "/{id_clinica}",
    response_model=ClinicaOut,
    summary="Atualizar dados da clínica",
)
async def atualizar_clinica(
    id_clinica: int,
    payload: ClinicaUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClinicaOut:
    clinica = await get_or_404(Clinica, id_clinica, db)

    # Verifica CNPJ duplicado se o campo foi alterado
    dados = payload.model_dump(exclude_unset=True)
    if "cnpj" in dados:
        existente = await db.scalar(
            select(Clinica).where(
                Clinica.cnpj == dados["cnpj"],
                Clinica.id_clinica != id_clinica,
            )
        )
        if existente:
            raise ConflitoDeNegocio(
                f"CNPJ {dados['cnpj']} já está em uso por outra clínica."
            )

    for campo, valor in dados.items():
        setattr(clinica, campo, valor)

    await db.flush()
    await db.refresh(clinica)
    return clinica  # type: ignore[return-value]


# ===========================================================================
# MÉDICOS VETERINÁRIOS (sub-recurso da clínica)
# ===========================================================================

@router.post(
    "/{id_clinica}/medicos",
    response_model=MedicoVeterinarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar médico na clínica",
)
async def cadastrar_medico(
    id_clinica: int,
    payload: MedicoVeterinarioCreate,
    db: AsyncSession = Depends(get_db),
) -> MedicoVeterinarioOut:
    """
    Cadastra um médico veterinário vinculado a uma clínica.

    Regra: CRMV deve ser único dentro da mesma clínica (um mesmo
    veterinário pode atuar em múltiplas clínicas com registros distintos).
    """
    # Garante que a clínica existe
    await get_or_404(Clinica, id_clinica, db)

    # Protege CRMV duplicado na mesma clínica com mensagem clara
    existente = await db.scalar(
        select(MedicoVeterinario).where(
            MedicoVeterinario.id_clinica == id_clinica,
            MedicoVeterinario.crmv == payload.crmv,
        )
    )
    if existente:
        raise ConflitoDeNegocio(
            f"CRMV '{payload.crmv}' já está cadastrado nesta clínica."
        )

    # Força id_clinica da URL (ignora qualquer valor no body)
    dados = payload.model_dump()
    dados["id_clinica"] = id_clinica

    medico = MedicoVeterinario(**dados)
    db.add(medico)
    await db.flush()
    await db.refresh(medico)
    return medico  # type: ignore[return-value]


@router.get(
    "/{id_clinica}/medicos",
    response_model=list[MedicoVeterinarioOut],
    summary="Listar médicos da clínica",
)
async def listar_medicos(
    id_clinica: int,
    db: AsyncSession = Depends(get_db),
) -> list[MedicoVeterinarioOut]:
    await get_or_404(Clinica, id_clinica, db)

    result = await db.execute(
        select(MedicoVeterinario)
        .where(MedicoVeterinario.id_clinica == id_clinica)
        .order_by(MedicoVeterinario.nome)
    )
    return result.scalars().all()  # type: ignore[return-value]


@router.get(
    "/{id_clinica}/medicos/{id_medico}",
    response_model=MedicoVeterinarioOut,
    summary="Buscar médico por ID",
)
async def buscar_medico(
    id_clinica: int,
    id_medico: int,
    db: AsyncSession = Depends(get_db),
) -> MedicoVeterinarioOut:
    await get_or_404(Clinica, id_clinica, db)
    medico = await get_or_404(MedicoVeterinario, id_medico, db)

    # Garante que o médico pertence à clínica solicitada (tenant isolation)
    if medico.id_clinica != id_clinica:
        from app.exceptions import RecursoNaoEncontrado
        raise RecursoNaoEncontrado(
            f"Médico {id_medico} não pertence à clínica {id_clinica}."
        )
    return medico  # type: ignore[return-value]
