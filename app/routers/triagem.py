"""
app/routers/triagem.py — O coração do sistema TrIAgem.

Este router processa o formulário de triagem preenchido pelo tutor e
executa a Regra de Urgência: sintomas críticos disparam imediatamente
um alerta vermelho no frontend da clínica, instruindo o tutor a buscar
o pronto-socorro veterinário.

REGRA ÉTICA FUNDAMENTAL:
O sistema detecta urgência, mas NUNCA emite diagnóstico.
Toda resposta usa linguagem de alerta, nunca de conclusão clínica.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_or_404
from app.exceptions import ConflitoDeNegocio, EstadoInvalido, TermoNaoAceito
from app.models import (
    Consulta,
    FormularioTriagem,
    Pet,
    RelatorioIA,
    Sintoma,
    Tutor,
    formulario_sintoma,
)
from app.schemas import (
    FormularioTriagemCreate,
    FormularioTriagemOut,
    RelatorioIAOut,
)

router = APIRouter(prefix="/triagem", tags=["Triagem"])


# ---------------------------------------------------------------------------
# Schemas de resposta internos (não poluem schemas.py com acoplamento de router)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, ConfigDict
from typing import Optional


class RespostaTriagem(BaseModel):
    """
    Resposta do endpoint de submissão da triagem.

    urgencia_detectada=True aciona o alerta vermelho no frontend.
    O backend nunca diz 'o animal tem X' — apenas 'sintomas de urgência presentes'.
    """
    model_config = ConfigDict(from_attributes=True)

    formulario: FormularioTriagemOut
    urgencia_detectada: bool
    sintomas_urgencia: list[str]
    mensagem_para_tutor: str
    acao_recomendada: str


class RespostaRelatorio(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relatorio: RelatorioIAOut
    consulta_id: int
    urgencia: bool


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

MENSAGEM_URGENCIA_ATIVA = (
    "⚠️ ATENÇÃO: Foram identificados sintomas que requerem avaliação imediata. "
    "Por favor, dirija-se ao pronto-socorro veterinário mais próximo agora. "
    "Não aguarde a consulta agendada."
)

MENSAGEM_URGENCIA_INATIVA = (
    "Triagem recebida com sucesso. O veterinário revisará as informações "
    "antes do atendimento. Aguarde ser chamado."
)

ACAO_EMERGENCIA = "PRONTO_SOCORRO_IMEDIATO"
ACAO_NORMAL = "AGUARDAR_ATENDIMENTO"


# ===========================================================================
# ENDPOINTS
# ===========================================================================

@router.post(
    "/{id_consulta}/submeter",
    response_model=RespostaTriagem,
    status_code=status.HTTP_201_CREATED,
    summary="Tutor submete o formulário de triagem",
)
async def submeter_triagem(
    id_consulta: int,
    payload: FormularioTriagemCreate,
    db: AsyncSession = Depends(get_db),
) -> RespostaTriagem:
    """
    Recebe e persiste o formulário de triagem preenchido pelo tutor.

    Fluxo de validações (em ordem de severidade):
    1. Consulta deve existir e estar 'agendada' ou 'em_andamento'
    2. Tutor do pet deve ter aceitado o termo de segurança (LGPD)
    3. Formulário não pode ser duplicado para a mesma consulta
    4. Sintomas informados devem existir no catálogo
    5. [REGRA DE URGÊNCIA] Verifica alerta_urgencia nos sintomas selecionados

    A flag `urgencia_detectada` deve ser consumida pelo frontend para
    exibir alerta vermelho imediato e bloquear o fluxo normal.
    """

    # --- 1. Valida consulta e seu estado ---
    consulta = await db.execute(
        select(Consulta)
        .options(selectinload(Consulta.pet).selectinload(Pet.tutor))
        .where(Consulta.id_consulta == id_consulta)
    )
    consulta = consulta.scalar_one_or_none()
    if consulta is None:
        from app.exceptions import RecursoNaoEncontrado
        raise RecursoNaoEncontrado(f"Consulta {id_consulta} não encontrada.")

    if consulta.status not in ("agendada", "em_andamento"):
        raise EstadoInvalido(
            f"Não é possível submeter triagem para uma consulta com "
            f"status '{consulta.status}'. "
            "A consulta precisa estar 'agendada' ou 'em_andamento'."
        )

    # --- 2. Valida aceite do termo de segurança (LGPD) ---
    tutor: Tutor = consulta.pet.tutor
    if not tutor.aceitou_termo_seguranca:
        raise TermoNaoAceito()

    # --- 3. Impede formulário duplicado (1:1 com consulta) ---
    formulario_existente = await db.scalar(
        select(FormularioTriagem).where(
            FormularioTriagem.id_consulta == id_consulta
        )
    )
    if formulario_existente:
        raise ConflitoDeNegocio(
            f"Já existe um formulário de triagem para a consulta {id_consulta} "
            f"(id_formulario={formulario_existente.id_formulario}). "
            "Não é permitido resubmeter a triagem."
        )

    # --- 4. Valida e carrega sintomas do catálogo ---
    sintomas_db: list[Sintoma] = []
    if payload.sintoma_ids:
        result = await db.execute(
            select(Sintoma).where(Sintoma.id_sintoma.in_(payload.sintoma_ids))
        )
        sintomas_db = list(result.scalars().all())

        # Detecta IDs inválidos
        ids_encontrados = {s.id_sintoma for s in sintomas_db}
        ids_invalidos = set(payload.sintoma_ids) - ids_encontrados
        if ids_invalidos:
            raise EstadoInvalido(
                f"Sintomas com IDs inválidos: {sorted(ids_invalidos)}. "
                "Verifique o catálogo de sintomas disponíveis."
            )

    # --- 5. Persiste o formulário ---
    dados_formulario = payload.model_dump(exclude={"sintoma_ids"})
    dados_formulario["id_consulta"] = id_consulta
    dados_formulario["submetido_em"] = datetime.now(timezone.utc)

    formulario = FormularioTriagem(**dados_formulario)
    formulario.sintomas = sintomas_db  # ORM cuida da tabela N:N
    db.add(formulario)
    await db.flush()
    await db.refresh(formulario, ["sintomas"])

    # --- REGRA DE URGÊNCIA ---
    # Verifica se algum sintoma selecionado possui alerta de urgência
    sintomas_criticos = [
        s.nome_sintoma for s in sintomas_db if s.alerta_urgencia
    ]
    urgencia_detectada = len(sintomas_criticos) > 0

    # Monta resposta orientada ao contexto (tutor no celular)
    if urgencia_detectada:
        mensagem = MENSAGEM_URGENCIA_ATIVA
        acao = ACAO_EMERGENCIA
    else:
        mensagem = MENSAGEM_URGENCIA_INATIVA
        acao = ACAO_NORMAL

    # Carrega formulário com sintomas para serialização
    formulario_out = FormularioTriagemOut.model_validate(formulario)

    return RespostaTriagem(
        formulario=formulario_out,
        urgencia_detectada=urgencia_detectada,
        sintomas_urgencia=sintomas_criticos,
        mensagem_para_tutor=mensagem,
        acao_recomendada=acao,
    )


@router.get(
    "/{id_consulta}",
    response_model=FormularioTriagemOut,
    summary="Buscar formulário de triagem de uma consulta",
)
async def buscar_triagem(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> FormularioTriagemOut:
    """
    Retorna o formulário de triagem preenchido pelo tutor.
    Usado pelo veterinário para revisão pré-consulta.
    """
    await get_or_404(Consulta, id_consulta, db)

    result = await db.execute(
        select(FormularioTriagem)
        .options(selectinload(FormularioTriagem.sintomas))
        .where(FormularioTriagem.id_consulta == id_consulta)
    )
    formulario = result.scalar_one_or_none()
    if formulario is None:
        from app.exceptions import RecursoNaoEncontrado
        raise RecursoNaoEncontrado(
            f"Nenhuma triagem submetida para a consulta {id_consulta} ainda."
        )
    return formulario  # type: ignore[return-value]


@router.get(
    "/{id_consulta}/relatorio",
    response_model=RelatorioIAOut,
    summary="Buscar relatório de IA da consulta",
)
async def buscar_relatorio(
    id_consulta: int,
    db: AsyncSession = Depends(get_db),
) -> RelatorioIAOut:
    """
    Retorna o relatório estruturado gerado pela IA a partir da triagem.

    Endpoint consumido pelo painel do veterinário. O relatório é gerado
    de forma assíncrona após a submissão da triagem (etapa futura de integração IA).

    LEMBRETE ÉTICO: o relatório apresenta pontos de investigação,
    nunca diagnósticos.
    """
    await get_or_404(Consulta, id_consulta, db)

    # Busca via formulário (relação 1:1 consulta→formulário→relatorio)
    result = await db.execute(
        select(RelatorioIA)
        .join(FormularioTriagem, RelatorioIA.id_formulario == FormularioTriagem.id_formulario)
        .where(FormularioTriagem.id_consulta == id_consulta)
    )
    relatorio = result.scalar_one_or_none()
    if relatorio is None:
        from app.exceptions import RecursoNaoEncontrado
        raise RecursoNaoEncontrado(
            f"Relatório de IA ainda não disponível para a consulta {id_consulta}. "
            "O processamento pode estar em andamento."
        )
    return relatorio  # type: ignore[return-value]


# ===========================================================================
# CATÁLOGO DE SINTOMAS (público — consumido pelo formulário mobile do tutor)
# ===========================================================================

@router.get(
    "/sintomas/catalogo",
    response_model=list[dict],
    summary="Listar catálogo de sintomas disponíveis",
    tags=["Sintomas"],
)
async def listar_sintomas(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Retorna o catálogo de sintomas para exibir no formulário mobile do tutor.

    Os sintomas com alerta_urgencia=True são exibidos com destaque especial
    no frontend para que o tutor os identifique facilmente.
    """
    result = await db.execute(
        select(Sintoma).order_by(Sintoma.alerta_urgencia.desc(), Sintoma.nome_sintoma)
    )
    sintomas = result.scalars().all()
    return [
        {
            "id_sintoma": s.id_sintoma,
            "nome_sintoma": s.nome_sintoma,
            "alerta_urgencia": s.alerta_urgencia,
            # Hint visual para o frontend mobile
            "nivel": "EMERGENCIA" if s.alerta_urgencia else "NORMAL",
        }
        for s in sintomas
    ]
