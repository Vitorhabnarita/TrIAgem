"""
app/dependencies.py — Helpers reutilizáveis, com ESCOPO DE TENANT embutido (RN-004).

Toda busca de entidade de negócio passa por aqui com o id_clinica do token,
de modo que um recurso de outra clínica é indistinguível de um inexistente (404).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import RecursoNaoEncontrado
from app.models import Consulta, FormularioTriagem, Pet
from app.security import PAPEL_MEDICO, UsuarioAtual


def agora_utc() -> datetime:
    """Único ponto de geração de timestamps do sistema (RN-003): sempre UTC com tzinfo."""
    return datetime.now(timezone.utc)


def garantir_utc(dt: datetime) -> datetime:
    """Normaliza datetimes recebidos/lidos para UTC com timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def carregar_consulta(
    db: AsyncSession,
    id_consulta: int,
    user: UsuarioAtual,
    *,
    bloquear: bool = False,
    detalhada: bool = False,
    apenas_proprias: bool = False,
) -> Consulta:
    """
    Carrega a consulta SOMENTE se pertencer à clínica do usuário.
    - bloquear: SELECT ... FOR UPDATE (evita corrida em iniciar/finalizar com duplo clique)
    - detalhada: eager loading de pet→tutor, médico, formulário→sintomas, relatório
    - apenas_proprias: médico só enxerga as próprias consultas
    """
    stmt = select(Consulta).where(
        Consulta.id_consulta == id_consulta,
        Consulta.id_clinica == user.id_clinica,
    )
    if apenas_proprias and user.papel == PAPEL_MEDICO:
        stmt = stmt.where(Consulta.id_medico == user.id_medico)
    if detalhada:
        stmt = stmt.options(
            selectinload(Consulta.pet).selectinload(Pet.tutor),
            selectinload(Consulta.medico),
            selectinload(Consulta.formulario).selectinload(FormularioTriagem.sintomas),
            selectinload(Consulta.formulario).selectinload(FormularioTriagem.relatorio),
        )
    if bloquear:
        stmt = stmt.with_for_update(of=Consulta)

    consulta: Optional[Consulta] = (await db.execute(stmt)).scalar_one_or_none()
    if consulta is None:
        raise RecursoNaoEncontrado(f"Consulta {id_consulta} não encontrada.")
    return consulta
