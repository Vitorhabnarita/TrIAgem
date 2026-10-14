"""
app/routers/triagem.py — Painel clínico: Briefing Estruturado de Triagem (médico/gestor).

Entrega o Relatório Clínico Prévio + dados brutos do formulário para leitura antes da consulta.
REGRA ÉTICA: o briefing apresenta pontos de Investigação Inicial, nunca diagnósticos.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import carregar_consulta
from app.exceptions import EstadoInvalido
from app.schemas import (
    BriefingOut,
    FormularioOut,
    MedicoMini,
    PacienteOut,
    RelatorioOut,
    TutorOut,
)
from app.security import PAPEL_GESTOR, PAPEL_MEDICO, PAPEL_RECEPCAO, UsuarioAtual, exigir_papeis
from app.services.triagem_service import processar_ia_em_background

router = APIRouter(prefix="/triagem", tags=["Painel Clínico"])


@router.get(
    "/{id_consulta}/briefing",
    response_model=BriefingOut,
    summary="Briefing Estruturado de Triagem da consulta",
)
async def briefing(
    id_consulta: int,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_MEDICO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> BriefingOut:
    c = await carregar_consulta(
        db, id_consulta, user, detalhada=True, apenas_proprias=True
    )
    form = c.formulario
    rel = form.relatorio if form else None

    sintomas_urg = [s.nome_sintoma for s in form.sintomas if s.alerta_urgencia] if form else []
    # RN-001: determinístico OR semântico
    urgencia = bool(form and (form.urgencia_deterministica or (rel and rel.flag_urgencia_detectada)))

    return BriefingOut(
        id_consulta=c.id_consulta,
        status=c.status,
        agendada_para=c.agendada_para,
        inicio_consulta=c.inicio_consulta,
        fim_consulta=c.fim_consulta,
        medico=MedicoMini.model_validate(c.medico),
        pet=PacienteOut.model_validate(c.pet),
        tutor=TutorOut.model_validate(c.pet.tutor),
        triagem_preenchida=form is not None,
        formulario=FormularioOut.model_validate(form) if form else None,
        relatorio=RelatorioOut.model_validate(rel) if rel else None,
        urgencia=urgencia,
        sintomas_urgencia=sintomas_urg,
        status_ia=form.status_ia if form else None,
        medicamento_continuo=form.medicamento_continuo if form else None,
        benchmark_minutos=settings.roi_benchmark_minutos,
    )


@router.post(
    "/{id_consulta}/reprocessar-ia",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reprocessar o Relatório Clínico Prévio (ex.: IA indisponível)",
)
async def reprocessar(
    id_consulta: int,
    background: BackgroundTasks,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_MEDICO, PAPEL_GESTOR, PAPEL_RECEPCAO)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    c = await carregar_consulta(db, id_consulta, user, detalhada=True, apenas_proprias=True)
    if c.formulario is None:
        raise EstadoInvalido("Não há Triagem Pré-Consulta preenchida para reprocessar.")
    c.formulario.status_ia = "pendente"
    id_formulario = c.formulario.id_formulario
    await db.commit()
    background.add_task(processar_ia_em_background, id_formulario)
    return {"mensagem": "Reprocessamento iniciado.", "status_ia": "pendente"}
