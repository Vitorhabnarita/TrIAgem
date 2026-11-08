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
    AcionarEmergenciaIn,
    AcionarEmergenciaOut,
    PetPublicoOut,
    ProtocoloEmergenciaPublicoOut,
    ResultadoTutorOut,
    SintomaPublicoOut,
    TriagemContextoOut,
    TriagemSubmissao,
    TriagemSubmissaoOut,
)
from app.services import emergencia, links
from app.services.guardrails import (
    classificar_emergencia,
    detectar_termos_criticos,
    primeiros_socorros_para,
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
        sintomas=[
            SintomaPublicoOut(
                id_sintoma=s.id_sintoma, nome_sintoma=s.nome_sintoma,
                alerta_urgencia=s.alerta_urgencia, categoria=s.categoria,
                categoria_emergencia=(
                    (classificar_emergencia(s.nome_sintoma) or "GERAL") if s.alerta_urgencia else None
                ),
            )
            for s in sintomas
        ],
        texto_termo=TEXTO_TERMO,
        emergencia=ProtocoloEmergenciaPublicoOut(**emergencia.protocolo_publico(clinica)),
        modalidade_emergencia=c.modalidade_emergencia,
    )


def _registrar_modalidade(
    consulta: Consulta, clinica: Clinica, modalidade: str, localizacao: str | None
) -> None:
    """
    RN-001 v2.0 — grava a logística de emergência na consulta (topo da fila da recepção/médico).
    O RESGATE_SOLICITADO nunca é rebaixado para EMERGENCIA_A_CAMINHO (a clínica já mobilizou o veículo).
    """
    if modalidade == "RESGATE_SOLICITADO":
        if not clinica.possui_veiculo_resgate:
            raise EstadoInvalido(
                "Esta clínica não possui veículo de resgate. Use 'Estou a caminho' ou procure o "
                "Hospital Veterinário 24h mais próximo."
            )
        if not localizacao:
            raise EstadoInvalido("Informe sua localização (GPS ou endereço) para solicitar o resgate.")
    if consulta.modalidade_emergencia != "RESGATE_SOLICITADO" or modalidade == "RESGATE_SOLICITADO":
        consulta.modalidade_emergencia = modalidade
    if localizacao:
        consulta.localizacao_gps_tutor = localizacao


@router.post(
    "/{token}/acionar-emergencia",
    response_model=AcionarEmergenciaOut,
    summary="Tutor aciona a emergência: 'Estou a caminho' ou 'Solicitar veículo de resgate'",
    dependencies=[Depends(limitar("pub-emerg", maximo=10, janela_segundos=60))],
)
async def acionar_emergencia(
    token: str, payload: AcionarEmergenciaIn, db: AsyncSession = Depends(get_db)
) -> AcionarEmergenciaOut:
    """
    Registro INSTANTÂNEO (RN-001 v2.0): não exige o formulário completo. Grava a modalidade e a
    localização na consulta (a recepção e o médico veem o paciente no topo da fila) e devolve os
    links de rota, o WhatsApp de resgate (com o Google Maps do animal) e o "O que NÃO fazer".
    Se a triagem já foi enviada, também grava a auditoria (ciência do risco e hora do alerta).
    """
    consulta = await _consulta_por_token(db, token, bloquear=True)
    estado = _estado(consulta)
    if estado == "cancelada":
        raise EstadoInvalido("Esta consulta foi cancelada pela clínica. Ligue para a clínica.")
    if estado == "expirada":
        raise LinkExpirado()

    clinica = await db.get(Clinica, consulta.id_clinica)
    _registrar_modalidade(consulta, clinica, payload.modalidade, payload.localizacao_gps_tutor)

    if consulta.formulario is not None:
        f = consulta.formulario
        f.ciente_risco_morte = f.ciente_risco_morte or payload.ciente_risco_morte
        f.alerta_critico_exibido_em = f.alerta_critico_exibido_em or emergencia.instante_alerta_confiavel(
            payload.alerta_critico_exibido_em
        )
    await db.commit()

    localizacao = consulta.localizacao_gps_tutor
    maps_url = links.maps_url_localizacao(localizacao)
    modalidade = consulta.modalidade_emergencia
    wa = (
        links.whatsapp_resgate_url(
            telefone_emergencia=clinica.telefone_emergencia, clinica_nome=clinica.nome_fantasia,
            tutor_nome=consulta.pet.tutor.nome, pet_nome=consulta.pet.nome, maps_url=maps_url,
        )
        if modalidade == "RESGATE_SOLICITADO" else None
    )
    return AcionarEmergenciaOut(
        modalidade_emergencia=modalidade,  # type: ignore[arg-type]
        localizacao_gps_tutor=localizacao,
        maps_url_tutor=maps_url,
        whatsapp_resgate_url=wa,
        rota_clinica=links.rota_clinica_urls(clinica.endereco_completo, clinica.nome_fantasia),
        whatsapp_plantao=clinica.telefone_emergencia,
        primeiros_socorros_negativos=primeiros_socorros_para(payload.categorias_emergencia),
        mensagem_para_tutor=(
            "Veículo de resgate solicitado. A equipe foi avisada com a sua localização e está a caminho. "
            "Mantenha o telefone por perto e siga as orientações do que NÃO fazer."
            if modalidade == "RESGATE_SOLICITADO"
            else "Equipe de emergência avisada! O Box de Emergência será preparado para a sua chegada. "
                 "Siga as orientações do que NÃO fazer e dirija com segurança."
        ),
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

    # --- RN-001 v2.0 (gatilho determinístico): sintoma de urgência OU termo crítico no relato livre
    #     OU emergência já acionada pelo tutor (a/b/c do disjuntor) ---
    sintomas_urgencia = [s.nome_sintoma for s in sintomas if s.alerta_urgencia]
    termos_criticos = detectar_termos_criticos(payload.relato_livre_tutor)
    modalidade_final = payload.modalidade_emergencia or consulta.modalidade_emergencia
    urgencia = bool(sintomas_urgencia or termos_criticos or modalidade_final)
    clinica = await db.get(Clinica, consulta.id_clinica)
    if payload.modalidade_emergencia:
        _registrar_modalidade(
            consulta, clinica, payload.modalidade_emergencia,
            payload.localizacao_gps_tutor or consulta.localizacao_gps_tutor,
        )

    # --- Consentimento LGPD (prova com timestamp) ---
    tutor: Tutor = consulta.pet.tutor
    tutor.aceitou_termo_seguranca = True
    tutor.termo_aceito_em = agora_utc()

    dados = payload.model_dump(
        exclude={"aceite_termo", "sintoma_ids", "modalidade_emergencia", "localizacao_gps_tutor",
                 "alerta_critico_exibido_em"}
    )
    formulario = FormularioTriagem(
        id_consulta=consulta.id_consulta,
        urgencia_deterministica=urgencia,
        status_ia="pendente",
        alerta_critico_exibido_em=(
            emergencia.instante_alerta_confiavel(payload.alerta_critico_exibido_em)
            if urgencia and (payload.alerta_critico_exibido_em or payload.ciente_risco_morte) else None
        ),
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

    maps_url = links.maps_url_localizacao(consulta.localizacao_gps_tutor)
    categorias = [classificar_emergencia(n) or "GERAL" for n in sintomas_urgencia]
    categorias += [classificar_emergencia(t) for t in termos_criticos]
    return TriagemSubmissaoOut(
        urgencia_detectada=urgencia,
        sintomas_urgencia=sintomas_urgencia,
        acao_recomendada=ACAO_EMERGENCIA if urgencia else ACAO_NORMAL,
        mensagem_para_tutor=MSG_URGENCIA if urgencia else MSG_NORMAL,
        status_ia="pendente",
        primeiros_socorros_negativos=primeiros_socorros_para(categorias) if urgencia else {},
        termos_criticos_relato=termos_criticos,
        modalidade_emergencia=consulta.modalidade_emergencia,
        maps_url_tutor=maps_url,
        whatsapp_resgate_url=(
            links.whatsapp_resgate_url(
                telefone_emergencia=clinica.telefone_emergencia, clinica_nome=clinica.nome_fantasia,
                tutor_nome=tutor.nome, pet_nome=consulta.pet.nome, maps_url=maps_url,
            )
            if consulta.modalidade_emergencia == "RESGATE_SOLICITADO" else None
        ),
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
    await db.refresh(form, ["relatorio", "sintomas"])
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
        primeiros_socorros_negativos=(
            primeiros_socorros_para(
                [classificar_emergencia(s.nome_sintoma) or "GERAL" for s in form.sintomas if s.alerta_urgencia]
                + [classificar_emergencia(t) for t in detectar_termos_criticos(form.relato_livre_tutor)]
            ) if urgencia else {}
        ),
        modalidade_emergencia=c.modalidade_emergencia,
    )

