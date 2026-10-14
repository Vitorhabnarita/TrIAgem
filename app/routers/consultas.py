"""
app/routers/consultas.py — Agenda, fila da recepção e cronômetro de consulta (RN-003).

Todas as queries são escopadas por id_clinica do token (RN-004).
Máquina de estados:  agendada → em_andamento → finalizada
                     agendada|em_andamento → cancelada
Timestamps: sempre UTC (dependencies.agora_utc), com SELECT ... FOR UPDATE nas transições
para evitar corrida por duplo clique.
"""

from datetime import date, datetime, time, timedelta
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import settings
from app.database import get_db
from app.dependencies import agora_utc, carregar_consulta, garantir_utc
from app.exceptions import ConflitoDeNegocio, EstadoInvalido, RecursoNaoEncontrado
from app.models import (
    Clinica,
    Consulta,
    FormularioTriagem,
    MedicoVeterinario,
    Pet,
    RelatorioIA,
    Tutor,
)
from app.schemas import (
    ConsultaAgendar,
    ConsultaFilaItem,
    ConsultaFinalizadaOut,
    ConsultaStatusOut,
    MedicoMini,
)
from app.security import (
    PAPEL_GESTOR,
    PAPEL_MEDICO,
    PAPEL_RECEPCAO,
    UsuarioAtual,
    exigir_papeis,
    gerar_token_triagem,
    usuario_atual,
)
from app.services import links
from app.services.roi import duracao_minutos, minutos_economizados

router = APIRouter(prefix="/consultas", tags=["Consultas"])

STATUS_VALIDOS = {"agendada", "em_andamento", "finalizada", "cancelada"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _janela_do_dia(dia: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(settings.timezone_clinica)
    ini = datetime.combine(dia, time.min, tzinfo=tz)
    return ini, ini + timedelta(days=1)


def _montar_item(c: Consulta, pet: Pet, tutor: Tutor, medico: MedicoVeterinario,
                 form: Optional[FormularioTriagem], rel: Optional[RelatorioIA],
                 clinica_nome: str) -> ConsultaFilaItem:
    # RN-001: determinístico OU semântico (IA)
    urgencia = bool(form and (form.urgencia_deterministica or (rel and rel.flag_urgencia_detectada)))
    if form is None:
        st = "pendente"
    elif urgencia:
        st = "urgencia"
    else:
        st = "preenchido"

    nivel = rel.nivel_prioridade if rel else ("EMERGENCIA" if urgencia else None)
    cor = rel.cor_prioridade if rel else ("VERMELHO" if urgencia else None)

    dur = eco = None
    if c.inicio_consulta and c.fim_consulta:
        try:
            dur = duracao_minutos(c.inicio_consulta, c.fim_consulta)
            eco = minutos_economizados(dur, settings.roi_benchmark_minutos, form is not None)
        except ValueError:
            pass

    return ConsultaFilaItem(
        id_consulta=c.id_consulta,
        status=c.status,
        agendada_para=c.agendada_para,
        pet_nome=pet.nome,
        especie=pet.especie,
        pet_raca=pet.raca,
        pet_sexo=pet.sexo,
        pet_idade=pet.idade_texto,
        pet_peso_kg=float(pet.peso_kg) if pet.peso_kg is not None else None,
        pet_porte=pet.porte,
        pet_status_reprodutivo=pet.status_reprodutivo,
        tutor_nome=tutor.nome,
        tutor_telefone=tutor.telefone,
        medico=MedicoMini(id_medico=medico.id_medico, nome=medico.nome),
        status_triagem=st,
        urgencia=urgencia,
        nivel_prioridade=nivel,
        cor_prioridade=cor,
        status_ia=form.status_ia if form else None,
        link_triagem=links.link_triagem(c.token_triagem),
        whatsapp_url=links.whatsapp_url(
            token=c.token_triagem, tutor_nome=tutor.nome, telefone=tutor.telefone,
            pet_nome=pet.nome, clinica_nome=clinica_nome,
        ),
        inicio_consulta=c.inicio_consulta,
        fim_consulta=c.fim_consulta,
        duracao_minutos=dur,
        minutos_economizados=eco,
    )


async def _item_por_id(db: AsyncSession, id_consulta: int, user: UsuarioAtual) -> ConsultaFilaItem:
    itens = await _consultar_fila(db, user, id_consulta=id_consulta)
    if not itens:
        raise RecursoNaoEncontrado(f"Consulta {id_consulta} não encontrada.")
    return itens[0]


async def _consultar_fila(
    db: AsyncSession,
    user: UsuarioAtual,
    *,
    dia: Optional[date] = None,
    id_medico: Optional[int] = None,
    status_filtro: Optional[str] = None,
    id_consulta: Optional[int] = None,
) -> list[ConsultaFilaItem]:
    stmt = (
        select(Consulta, Pet, Tutor, MedicoVeterinario, FormularioTriagem, RelatorioIA, Clinica.nome_fantasia)
        .join(Pet, Pet.id_pet == Consulta.id_pet)
        .join(Tutor, Tutor.id_tutor == Pet.id_tutor)
        .join(MedicoVeterinario, MedicoVeterinario.id_medico == Consulta.id_medico)
        .join(Clinica, Clinica.id_clinica == Consulta.id_clinica)
        .outerjoin(FormularioTriagem, FormularioTriagem.id_consulta == Consulta.id_consulta)
        .outerjoin(RelatorioIA, RelatorioIA.id_formulario == FormularioTriagem.id_formulario)
        .where(Consulta.id_clinica == user.id_clinica)  # RN-004
    )
    if user.papel == PAPEL_MEDICO:
        stmt = stmt.where(Consulta.id_medico == user.id_medico)
    elif id_medico:
        stmt = stmt.where(Consulta.id_medico == id_medico)
    if id_consulta:
        stmt = stmt.where(Consulta.id_consulta == id_consulta)
    if status_filtro:
        stmt = stmt.where(Consulta.status == status_filtro)
    if dia:
        ini, fim = _janela_do_dia(dia)
        ref = func.coalesce(Consulta.agendada_para, Consulta.criada_em)
        stmt = stmt.where(ref >= ini, ref < fim)
    stmt = stmt.order_by(func.coalesce(Consulta.agendada_para, Consulta.criada_em))

    linhas = (await db.execute(stmt)).all()
    itens = [_montar_item(c, p, t, m, f, r, nome) for c, p, t, m, f, r, nome in linhas]
    # Urgências primeiro (fila do topo), depois em andamento, depois por horário
    ordem = {"em_andamento": 0, "agendada": 1, "finalizada": 2, "cancelada": 3}
    itens.sort(key=lambda i: (not (i.urgencia and i.status in ("agendada", "em_andamento")),
                              ordem.get(i.status, 9)))
    return itens


# ---------------------------------------------------------------------------
# Agenda / fila
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ConsultaFilaItem,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar consulta e gerar link da Triagem Pré-Consulta",
)
async def agendar_consulta(
    payload: ConsultaAgendar,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_RECEPCAO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> ConsultaFilaItem:
    """
    Agendamento rápido: reaproveita o tutor (por telefone) e o pet (por nome) dentro da MESMA clínica
    ou cria novos; gera o token único (256 bits) do link do WhatsApp.
    """
    medico = await db.get(MedicoVeterinario, payload.id_medico)
    if medico is None or medico.id_clinica != user.id_clinica:   # RN-004
        raise RecursoNaoEncontrado("Médico veterinário não encontrado nesta clínica.")

    tutor = await db.scalar(
        select(Tutor).where(
            Tutor.id_clinica == user.id_clinica, Tutor.telefone == payload.tutor.telefone
        )
    )
    if tutor is None:
        tutor = Tutor(id_clinica=user.id_clinica, nome=payload.tutor.nome.strip(),
                      telefone=payload.tutor.telefone, aceitou_termo_seguranca=False)
        db.add(tutor)
        await db.flush()

    pet = await db.scalar(
        select(Pet).where(Pet.id_tutor == tutor.id_tutor,
                          func.lower(Pet.nome) == payload.pet.nome.strip().lower())
    )
    if pet is None:
        pet = Pet(id_tutor=tutor.id_tutor, **payload.pet.model_dump())
        pet.nome = pet.nome.strip()
        db.add(pet)
        await db.flush()

    aberta = await db.scalar(
        select(Consulta).where(
            Consulta.id_pet == pet.id_pet, Consulta.status.in_(["agendada", "em_andamento"])
        )
    )
    if aberta:
        raise ConflitoDeNegocio(
            f"{pet.nome} já possui uma consulta em aberto (#{aberta.id_consulta}, status "
            f"'{aberta.status}'). Finalize ou cancele antes de agendar outra."
        )

    agora = agora_utc()
    consulta = Consulta(
        id_clinica=user.id_clinica,
        id_pet=pet.id_pet,
        id_medico=medico.id_medico,
        status="agendada",
        agendada_para=garantir_utc(payload.agendada_para) if payload.agendada_para else agora,
        token_triagem=gerar_token_triagem(),
        token_expira_em=agora + timedelta(hours=settings.token_triagem_validade_horas),
    )
    db.add(consulta)
    await db.flush()
    return await _item_por_id(db, consulta.id_consulta, user)


@router.get("/fila", response_model=list[ConsultaFilaItem],
            summary="Fila do dia (recepção, médico ou gestor)")
async def fila(
    data: Optional[date] = Query(None, description="Dia (fuso da clínica). Padrão: hoje."),
    id_medico: Optional[int] = Query(None, gt=0),
    status_consulta: Optional[Literal["agendada", "em_andamento", "finalizada", "cancelada"]] = Query(
        None, alias="status"
    ),
    user: UsuarioAtual = Depends(usuario_atual),
    db: AsyncSession = Depends(get_db),
) -> list[ConsultaFilaItem]:
    dia = data or datetime.now(ZoneInfo(settings.timezone_clinica)).date()
    return await _consultar_fila(db, user, dia=dia, id_medico=id_medico, status_filtro=status_consulta)


@router.get("/{id_consulta}", response_model=ConsultaFilaItem, summary="Resumo de uma consulta")
async def buscar_consulta(
    id_consulta: int, user: UsuarioAtual = Depends(usuario_atual), db: AsyncSession = Depends(get_db)
) -> ConsultaFilaItem:
    return await _item_por_id(db, id_consulta, user)


# ---------------------------------------------------------------------------
# Cronômetro (RN-003)
# ---------------------------------------------------------------------------

@router.patch("/{id_consulta}/iniciar", response_model=ConsultaStatusOut,
              summary="Iniciar consulta — grava inicio_consulta em UTC")
async def iniciar_consulta(
    id_consulta: int,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_MEDICO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> Consulta:
    consulta = await carregar_consulta(db, id_consulta, user, bloquear=True, apenas_proprias=True)

    if consulta.status == "em_andamento":
        raise EstadoInvalido("A consulta já foi iniciada.")
    if consulta.status == "finalizada":
        raise EstadoInvalido("Consulta já finalizada. Não é possível reiniciá-la.")
    if consulta.status == "cancelada":
        raise EstadoInvalido("Consulta cancelada não pode ser iniciada.")
    if consulta.status != "agendada":
        raise EstadoInvalido(f"Status desconhecido: '{consulta.status}'.")

    consulta.status = "em_andamento"
    consulta.inicio_consulta = agora_utc()
    await db.flush()
    await db.refresh(consulta)
    return consulta


@router.patch("/{id_consulta}/finalizar", response_model=ConsultaFinalizadaOut,
              summary="Finalizar consulta — grava fim_consulta em UTC e calcula o tempo economizado")
async def finalizar_consulta(
    id_consulta: int,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_MEDICO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> ConsultaFinalizadaOut:
    consulta = await carregar_consulta(db, id_consulta, user, bloquear=True, apenas_proprias=True)

    if consulta.status == "agendada":
        raise EstadoInvalido("A consulta ainda não foi iniciada. Inicie antes de finalizar.")
    if consulta.status == "finalizada":
        raise EstadoInvalido("A consulta já está finalizada.")
    if consulta.status == "cancelada":
        raise EstadoInvalido("Consulta cancelada não pode ser finalizada.")
    if consulta.inicio_consulta is None:
        raise EstadoInvalido("Consulta em andamento sem início registrado. Contate o suporte.")

    agora = agora_utc()
    try:
        duracao = duracao_minutos(consulta.inicio_consulta, agora)
    except ValueError:
        raise EstadoInvalido("Fim anterior ao início: relógio inconsistente. Tente novamente.") from None

    com_triagem = (
        await db.scalar(
            select(func.count(FormularioTriagem.id_formulario)).where(
                FormularioTriagem.id_consulta == consulta.id_consulta
            )
        )
    ) > 0
    economia = minutos_economizados(duracao, settings.roi_benchmark_minutos, com_triagem)

    consulta.status = "finalizada"
    consulta.fim_consulta = agora
    await db.flush()
    await db.refresh(consulta)

    return ConsultaFinalizadaOut(
        id_consulta=consulta.id_consulta,
        status=consulta.status,
        inicio_consulta=consulta.inicio_consulta,
        fim_consulta=consulta.fim_consulta,
        duracao_minutos=duracao,
        benchmark_minutos=settings.roi_benchmark_minutos,
        minutos_economizados=economia,
        com_triagem=com_triagem,
        mensagem=(
            f"Consulta finalizada em {duracao:g} min. "
            + (f"Economia estimada: {economia:g} min vs. benchmark de "
               f"{settings.roi_benchmark_minutos} min." if com_triagem
               else "Sem Triagem Pré-Consulta preenchida: não conta para o ROI.")
        ),
    )


@router.patch("/{id_consulta}/cancelar", response_model=ConsultaStatusOut,
              summary="Cancelar consulta")
async def cancelar_consulta(
    id_consulta: int,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_RECEPCAO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> Consulta:
    consulta = await carregar_consulta(db, id_consulta, user, bloquear=True)
    if consulta.status in ("finalizada", "cancelada"):
        raise EstadoInvalido(f"Consulta com status '{consulta.status}' não pode ser cancelada.")
    consulta.status = "cancelada"
    await db.flush()
    await db.refresh(consulta)
    return consulta


@router.post("/{id_consulta}/novo-link", response_model=ConsultaFilaItem,
             summary="Gerar novo link (invalida o anterior)")
async def renovar_link(
    id_consulta: int,
    user: UsuarioAtual = Depends(exigir_papeis(PAPEL_RECEPCAO, PAPEL_GESTOR)),
    db: AsyncSession = Depends(get_db),
) -> ConsultaFilaItem:
    consulta = await carregar_consulta(db, id_consulta, user, bloquear=True)
    if consulta.status in ("finalizada", "cancelada"):
        raise EstadoInvalido("Não é possível renovar o link de uma consulta encerrada.")
    consulta.token_triagem = gerar_token_triagem()
    consulta.token_expira_em = agora_utc() + timedelta(hours=settings.token_triagem_validade_horas)
    await db.flush()
    return await _item_por_id(db, id_consulta, user)
