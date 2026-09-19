"""
app/routers/consultas.py — Motor de consultas e medição de tempo.

Este router é o coração do argumento de marketing do TrIAgem:
cada consulta tem timestamps de início e fim que provam a economia
de tempo gerada pelo sistema de triagem digital.

Fluxo de estado:
  agendada → [iniciar] → em_andamento → [finalizar] → finalizada
                                      ↘ [cancelar]  → cancelada
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_or_404
from app.exceptions import ConflitoDeNegocio, EstadoInvalido
from app.models import Clinica, Consulta, MedicoVeterinario, Pet, Tutor
from app.schemas import (
    ConsultaCreate,
    ConsultaDetalhadaOut,
    ConsultaOut,
)

router = APIRouter(prefix="/consultas", tags=["Consultas"])


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _agora_utc() -> datetime:
    """Retorna datetime atual em UTC com timezone info."""
    return datetime.now(timezone.utc)


async def _buscar_consulta_detalhada(
    id_consulta: int, db: AsyncSession
) -> Consulta:
    """
    Busca consulta com eager loading de pet, médico e formulário.
    Evita N+1 queries nas respostas detalhadas.
    """
    result = await db.execute(
        select(Consulta)
        .options(
            selectinload(Consulta.pet),
            selectinload(Consulta.medico),
            selectinload(Consulta.formulario),
        )
        .where(Consulta.id_consulta == id_consulta)
    )
    consulta = result.scalar_one_or_none()
    if consulta is None:
        from app.exceptions import RecursoNaoEncontrado
        raise RecursoNaoEncontrado(f"Consulta {id_consulta} não encontrada.")
    return consulta


# ===========================================================================
# ENDPOINTS
# ===========================================================================

@router.post(
    "",
    response_model=ConsultaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar nova consulta",
)
async def agendar_consulta(
    payload: ConsultaCreate,
    db: AsyncSession = Depends(get_db),
) -> ConsultaOut:
    """
    Agenda uma consulta vinculando um pet a um médico.

    Validações:
    - Pet deve existir
    - Médico deve existir e pertencer à mesma clínica do tutor do pet
    - Não permite consultas duplicadas em aberto para o mesmo pet
    """
    # Carrega pet com tutor para cruzar clínica
    pet = await get_or_404(Pet, payload.id_pet, db)
    await db.refresh(pet, ["tutor"])
    medico = await get_or_404(MedicoVeterinario, payload.id_medico, db)

    # Isolamento de tenant: pet e médico devem ser da mesma clínica
    if pet.tutor.id_clinica != medico.id_clinica:
        raise EstadoInvalido(
            "O pet e o médico pertencem a clínicas diferentes. "
            "Não é possível criar a consulta."
        )

    # Bloqueia consultas abertas duplicadas para o mesmo pet
    consulta_aberta = await db.scalar(
        select(Consulta).where(
            Consulta.id_pet == payload.id_pet,
            Consulta.status.in_(["agendada", "em_andamento"]),
        )
    )
    if consulta_aberta:
        raise ConflitoDeNegocio(
            f"O pet já possui uma consulta em aberto (id={consulta_aberta.id_consulta}, "
            f"status='{consulta_aberta.status}'). Finalize-a antes de criar uma nova."
        )

    consulta = Consulta(
        id_pet=payload.id_pet,
        id_medico=payload.id_medico,
        status="agendada",
    )
    db.add(consulta)
    await db.flush()
    await db.refresh(consulta)
    return consulta  # type: ignore[return-value]


@router.get(
    "/{id_consulta}",
    response_model=ConsultaDetalhadaOut,
    summary="Buscar consulta detalhada",
)
async def buscar_consulta(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> ConsultaDetalhadaOut:
    """Retorna consulta com pet, médico, formulário e relatório (se existirem)."""
    return await _buscar_consulta_detalhada(id_consulta, db)  # type: ignore[return-value]


@router.patch(
    "/{id_consulta}/iniciar",
    response_model=ConsultaOut,
    summary="Iniciar consulta — grava timestamp de início",
)
async def iniciar_consulta(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> ConsultaOut:
    """
    Marca o início da consulta com timestamp UTC.

    Regras de estado:
    - Só pode iniciar uma consulta com status 'agendada'
    - 'em_andamento': já foi iniciada → erro claro
    - 'finalizada'/'cancelada': fluxo encerrado → erro claro

    O timestamp gravado aqui é a âncora do cálculo de tempo economizado.
    """
    consulta = await get_or_404(Consulta, id_consulta, db)

    match consulta.status:
        case "em_andamento":
            raise EstadoInvalido(
                f"Consulta já foi iniciada em "
                f"{consulta.inicio_consulta.strftime('%d/%m/%Y %H:%M:%S UTC')}."
            )
        case "finalizada":
            raise EstadoInvalido(
                "Consulta já foi finalizada. Não é possível reiniciá-la."
            )
        case "cancelada":
            raise EstadoInvalido(
                "Consulta cancelada não pode ser iniciada."
            )
        case "agendada":
            pass  # Estado válido — prossegue
        case _:
            raise EstadoInvalido(f"Status desconhecido: '{consulta.status}'.")

    consulta.status = "em_andamento"
    consulta.inicio_consulta = _agora_utc()

    await db.flush()
    await db.refresh(consulta)
    return consulta  # type: ignore[return-value]


@router.patch(
    "/{id_consulta}/finalizar",
    response_model=dict,
    summary="Finalizar consulta — grava timestamp de fim e calcula duração",
)
async def finalizar_consulta(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Marca o fim da consulta e calcula o tempo total em minutos.

    Regras de estado:
    - Só pode finalizar consultas 'em_andamento'
    - Retorna o tempo de duração — dado vital para o dashboard de ROI da clínica

    O campo `duracao_minutos` alimenta diretamente o argumento de marketing
    'economia de 15 min por consulta'.
    """
    consulta = await get_or_404(Consulta, id_consulta, db)

    match consulta.status:
        case "agendada":
            raise EstadoInvalido(
                "Consulta ainda não foi iniciada. "
                "Use PATCH /consultas/{id}/iniciar primeiro."
            )
        case "finalizada":
            raise EstadoInvalido("Consulta já está finalizada.")
        case "cancelada":
            raise EstadoInvalido("Consulta cancelada não pode ser finalizada.")
        case "em_andamento":
            pass  # Estado válido
        case _:
            raise EstadoInvalido(f"Status desconhecido: '{consulta.status}'.")

    agora = _agora_utc()
    consulta.status = "finalizada"
    consulta.fim_consulta = agora

    # Cálculo de duração — núcleo da métrica de ROI
    inicio = consulta.inicio_consulta
    if inicio.tzinfo is None:
        # Fallback: trata como UTC se veio sem timezone
        from datetime import timezone as tz
        inicio = inicio.replace(tzinfo=tz.utc)

    duracao_segundos = (agora - inicio).total_seconds()
    duracao_minutos = round(duracao_segundos / 60, 2)

    await db.flush()
    await db.refresh(consulta)

    return {
        "id_consulta": consulta.id_consulta,
        "status": consulta.status,
        "inicio_consulta": consulta.inicio_consulta,
        "fim_consulta": consulta.fim_consulta,
        "duracao_minutos": duracao_minutos,
        "mensagem": (
            f"Consulta finalizada. Duração: {duracao_minutos} minuto(s). "
            "Dado registrado para o relatório de eficiência."
        ),
    }


@router.patch(
    "/{id_consulta}/cancelar",
    response_model=ConsultaOut,
    summary="Cancelar consulta",
)
async def cancelar_consulta(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> ConsultaOut:
    """Cancela uma consulta agendada ou em andamento."""
    consulta = await get_or_404(Consulta, id_consulta, db)

    if consulta.status in ("finalizada", "cancelada"):
        raise EstadoInvalido(
            f"Consulta com status '{consulta.status}' não pode ser cancelada."
        )

    consulta.status = "cancelada"
    await db.flush()
    await db.refresh(consulta)
    return consulta  # type: ignore[return-value]


@router.get(
    "/pet/{id_pet}",
    response_model=list[ConsultaOut],
    summary="Listar consultas de um pet",
)
async def listar_consultas_pet(
    id_pet: int,
    db: AsyncSession = Depends(get_db),
) -> list[ConsultaOut]:
    """Retorna todas as consultas de um pet, ordenadas da mais recente."""
    await get_or_404(Pet, id_pet, db)

    result = await db.execute(
        select(Consulta)
        .where(Consulta.id_pet == id_pet)
        .order_by(Consulta.id_consulta.desc())
    )
    return result.scalars().all()  # type: ignore[return-value]
