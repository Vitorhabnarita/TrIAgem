"""
app/routers/publico.py — Jornada do Tutor (Triagem Pré-Consulta) via link único do WhatsApp.

Rotas PÚBLICAS, acessadas somente pelo token (256 bits). O tutor nunca vê IDs internos.
Segurança: rate limit por IP, validade do link, trava FOR UPDATE contra envio duplo,
validação estrita (RN-002) e IA em background (a falha da IA nunca bloqueia o tutor).

REGRA ÉTICA: o sistema detecta urgência, NUNCA emite diagnóstico.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import agora_utc, garantir_utc
from app.exceptions import ConflitoDeNegocio, EstadoInvalido, LinkExpirado, RecursoNaoEncontrado
from app.models import Clinica, Consulta, FormularioTriagem, Pet, Sintoma, Tutor
from app.ratelimit import limitar
from app.schemas import (
    PetPublicoOut,
    ResultadoTutorOut,
    SintomaPublicoOut,
    TriagemContextoOut,
    TriagemSubmissao,
    TriagemSubmissaoOut,
)
from app.services.triagem_service import processar_ia_em_background

router = APIRouter(prefix="/publico/triagem", tags=["Triagem Pré-Consulta (Tutor)"])

TEXTO_TERMO = (
    "Declaro que entendi que esta Triagem Pré-Consulta NÃO substitui atendimento de emergência: se meu "
    "animal estiver em risco, procurarei imediatamente um pronto-socorro veterinário. Autorizo o "
    "tratamento dos dados informados (meus e do meu animal) pela clínica e pelo sistema TrIAgem, "
    "inclusive o processamento por inteligência artificial, exclusivamente para organizar o "
    "atendimento, nos termos da LGPD (Lei 13.709/2018)."
)

MSG_URGENCIA = (
    "ATENÇÃO: foram assinalados sinais que exigem avaliação imediata. Leve seu animal agora ao "
    "pronto-socorro veterinário mais próximo. Não aguarde a consulta e não administre nenhum "
    "medicamento por conta própria. A clínica já foi avisada."
)
MSG_NORMAL = (
    "Triagem Pré-Consulta recebida! O médico veterinário lerá o Relatório Clínico Prévio antes do "
    "atendimento. Aguarde ser chamado. Não medique seu animal por conta própria."
)
ACAO_EMERGENCIA = "PRONTO_SOCORRO_IMEDIATO"
ACAO_NORMAL = "AGUARDAR_ATENDIMENTO"


async def _consulta_por_token(db: AsyncSession, token: str, *, bloquear: bool = False) -> Consulta:
    if not (20 <= len(token) <= 64):
        raise RecursoNaoEncontrado("Link inválido.")
    stmt = (
        select(Consulta)
        .options(
            selectinload(Consulta.pet).selectinload(Pet.tutor),
            selectinload(Consulta.formulario),
        )
        .where(Consulta.token_triagem == token)
    )
    if bloquear:
        stmt = stmt.with_for_update(of=Consulta)
    consulta = (await db.execute(stmt)).scalar_one_or_none()
    if consulta is None:
        raise RecursoNaoEncontrado("Link inválido ou inexistente.")
    return consulta


def _estado(c: Consulta) -> str:
    if c.status == "cancelada":
        return "cancelada"
    if c.formulario is not None:
        return "preenchida"
    if garantir_utc(c.token_expira_em) < agora_utc() or c.status == "finalizada":
        return "expirada"
    return "aguardando"


@router.get(
    "/{token}",
    response_model=TriagemContextoOut,
    summary="Contexto do formulário (clínica, pet, catálogo de sintomas)",
    dependencies=[Depends(limitar("pub-get", maximo=60, janela_segundos=60))],
)
async def contexto(token: str, db: AsyncSession = Depends(get_db)) -> TriagemContextoOut:
    c = await _consulta_por_token(db, token)
    clinica = await db.get(Clinica, c.id_clinica)
    estado = _estado(c)

    sintomas: list[Sintoma] = []
    if estado == "aguardando":
        res = await db.execute(
            select(Sintoma)
            .where(Sintoma.ativo.is_(True))
            .order_by(Sintoma.categoria, Sintoma.alerta_urgencia.desc(), Sintoma.nome_sintoma)
        )
        sintomas = list(res.scalars().all())

    return TriagemContextoOut(
        clinica_nome=clinica.nome_fantasia,
        segmento=clinica.segmento,
        tutor_primeiro_nome=c.pet.tutor.nome.strip().split(" ")[0],
        pet=PetPublicoOut.model_validate(c.pet),
        agendada_para=c.agendada_para,
        estado=estado,  # type: ignore[arg-type]
        sintomas=[SintomaPublicoOut.model_validate(s) for s in sintomas],
        texto_termo=TEXTO_TERMO,
    )


@router.post(
    "/{token}",
    response_model=TriagemSubmissaoOut,
    status_code=201,
    summary="Tutor envia a Triagem Pré-Consulta",
    dependencies=[Depends(limitar("pub-post", maximo=10, janela_segundos=60))],
)
async def submeter(
    token: str,
    payload: TriagemSubmissao,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> TriagemSubmissaoOut:
    consulta = await _consulta_por_token(db, token, bloquear=True)
    estado = _estado(consulta)
    if estado == "preenchida":
        raise ConflitoDeNegocio("A Triagem Pré-Consulta desta consulta já foi enviada. Obrigado!")
    if estado == "cancelada":
        raise EstadoInvalido("Esta consulta foi cancelada pela clínica.")
    if estado == "expirada":
        raise LinkExpirado()

    # --- Sintomas do catálogo (apenas ativos). IDs inválidos → erro claro ---
    sintomas: list[Sintoma] = []
    if payload.sintoma_ids:
        res = await db.execute(
            select(Sintoma).where(Sintoma.id_sintoma.in_(payload.sintoma_ids), Sintoma.ativo.is_(True))
        )
        sintomas = list(res.scalars().all())
        invalidos = set(payload.sintoma_ids) - {s.id_sintoma for s in sintomas}
        if invalidos:
            raise EstadoInvalido(f"Sintomas inválidos no checklist: {sorted(invalidos)}.")

    # --- RN-001 (gatilho determinístico) ---
    sintomas_urgencia = [s.nome_sintoma for s in sintomas if s.alerta_urgencia]
    urgencia = len(sintomas_urgencia) > 0

    # --- Consentimento LGPD (prova com timestamp) ---
    tutor: Tutor = consulta.pet.tutor
    tutor.aceitou_termo_seguranca = True
    tutor.termo_aceito_em = agora_utc()

    dados = payload.model_dump(exclude={"aceite_termo", "sintoma_ids"})
    formulario = FormularioTriagem(
        id_consulta=consulta.id_consulta,
        urgencia_deterministica=urgencia,
        status_ia="pendente",
        **dados,
    )
    formulario.sintomas = sintomas
    db.add(formulario)
    try:
        await db.flush()
    except IntegrityError:
        raise ConflitoDeNegocio("A Triagem Pré-Consulta desta consulta já foi enviada.") from None

    # Persiste ANTES de agendar a IA (a tarefa usa sessão própria)
    id_formulario = formulario.id_formulario
    await db.commit()
    background.add_task(processar_ia_em_background, id_formulario)

    return TriagemSubmissaoOut(
        urgencia_detectada=urgencia,
        sintomas_urgencia=sintomas_urgencia,
        acao_recomendada=ACAO_EMERGENCIA if urgencia else ACAO_NORMAL,
        mensagem_para_tutor=MSG_URGENCIA if urgencia else MSG_NORMAL,
        status_ia="pendente",
    )


@router.get(
    "/{token}/resultado",
    response_model=ResultadoTutorOut,
    summary="Resultado para o tutor (alerta de segurança gerado pela IA)",
    dependencies=[Depends(limitar("pub-res", maximo=60, janela_segundos=60))],
)
async def resultado(token: str, db: AsyncSession = Depends(get_db)) -> ResultadoTutorOut:
    """O frontend consulta a cada poucos segundos até `status_ia != 'pendente'`."""
    c = await _consulta_por_token(db, token)
    form = c.formulario
    if form is None:
        raise RecursoNaoEncontrado("A Triagem Pré-Consulta ainda não foi enviada.")
    await db.refresh(form, ["relatorio"])
    rel = form.relatorio

    # RN-001: o gatilho semântico (IA) também pode acionar o alerta vermelho
    urgencia = bool(form.urgencia_deterministica or (rel and rel.flag_urgencia_detectada))
    alerta = rel.alerta_seguranca_tutor if rel else None
    if urgencia and not alerta:
        alerta = MSG_URGENCIA

    return ResultadoTutorOut(
        status_ia=form.status_ia,  # type: ignore[arg-type]
        urgencia_detectada=urgencia,
        acao_recomendada=ACAO_EMERGENCIA if urgencia else ACAO_NORMAL,
        alerta_seguranca_tutor=alerta,
        nivel_prioridade=rel.nivel_prioridade if rel else ("EMERGENCIA" if urgencia else None),
    )

