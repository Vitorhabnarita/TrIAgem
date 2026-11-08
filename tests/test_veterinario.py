"""
tests/test_veterinario.py — Especialização veterinária do MVP (dados clínicos do pet, manejo preventivo,
busca de tutores para o agendamento rápido, login 1-click de demonstração e seed).

Complementa (sem alterar) as suítes de regras de negócio e unitárias.
"""

from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Consulta, Usuario
from tests.conftest import _seed, id_sintoma, payload_agendamento, payload_triagem


def _agendamento_vet(id_medico: int, **pet_extra) -> dict:
    p = payload_agendamento(id_medico, telefone="11988887777", pet="Simba")
    p["pet"].update({"especie": "Gato", "raca": "Persa", **pet_extra})
    return p


# ================================ Dados clínicos do pet ================================

async def test_dados_clinicos_do_pet_aparecem_na_fila_e_no_briefing(client, montar_clinica, ia):
    a = await montar_clinica()
    r = await client.post("/consultas", headers=a.recepcao, json=_agendamento_vet(
        a.id_medico, peso_kg=5.0, porte="Pequeno", status_reprodutivo="Castrado"))
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["pet_raca"] == "Persa" and item["pet_peso_kg"] == 5.0
    assert item["pet_porte"] == "Pequeno" and item["pet_status_reprodutivo"] == "Castrado"

    token = item["link_triagem"].rsplit("/", 1)[1]
    ctx = (await client.get(f"/publico/triagem/{token}")).json()
    assert ctx["pet"]["peso_kg"] == 5.0 and ctx["pet"]["status_reprodutivo"] == "Castrado"

    await client.post(f"/publico/triagem/{token}", json=payload_triagem())
    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["pet"]["peso_kg"] == 5.0 and b["pet"]["porte"] == "Pequeno"
    # os dados clínicos chegam ao contexto enviado à IA
    assert ia.chamadas[0].peso_kg == 5.0 and ia.chamadas[0].status_reprodutivo == "Castrado"


async def test_dados_clinicos_do_pet_sao_opcionais_e_validados(client, montar_clinica):
    a = await montar_clinica()
    ok = await client.post("/consultas", headers=a.recepcao, json=payload_agendamento(a.id_medico))
    assert ok.status_code == 201 and ok.json()["pet_peso_kg"] is None
    ruim = _agendamento_vet(a.id_medico, peso_kg=-3)
    ruim["tutor"]["telefone"] = "11977776666"
    assert (await client.post("/consultas", headers=a.recepcao, json=ruim)).status_code == 422
    ruim2 = _agendamento_vet(a.id_medico, status_reprodutivo="Talvez")
    ruim2["tutor"]["telefone"] = "11977775555"
    assert (await client.post("/consultas", headers=a.recepcao, json=ruim2)).status_code == 422


# ================================ Manejo preventivo (vacinas / ectoparasitas) ================================

async def test_manejo_preventivo_e_persistido_exibido_e_enviado_a_ia(client, montar_clinica, ia):
    a = await montar_clinica()
    r = await client.post("/consultas", json=payload_agendamento(a.id_medico), headers=a.recepcao)
    item = r.json()
    token = item["link_triagem"].rsplit("/", 1)[1]
    manejo = "Vacinas: V10 e antirrábica em dia. Antipulgas: em dia. Acesso à rua: sim. Contactantes: 2 gatos."
    assert (await client.post(f"/publico/triagem/{token}", json=payload_triagem(manejo_preventivo=manejo))).status_code == 201
    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["formulario"]["manejo_preventivo"] == manejo
    assert ia.chamadas[0].manejo_preventivo == manejo


async def test_manejo_preventivo_e_opcional(client, montar_clinica, ia):
    a = await montar_clinica()
    item = (await client.post("/consultas", json=payload_agendamento(a.id_medico), headers=a.recepcao)).json()
    token = item["link_triagem"].rsplit("/", 1)[1]
    assert (await client.post(f"/publico/triagem/{token}", json=payload_triagem())).status_code == 201
    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["formulario"]["manejo_preventivo"] is None


# ================================ Busca de tutores (agendamento rápido) ================================

async def test_busca_de_tutores_e_pets_e_escopada_por_clinica(client, montar_clinica):
    a = await montar_clinica("Clínica A")
    b = await montar_clinica("Clínica B")
    await client.post("/consultas", json=payload_agendamento(a.id_medico, telefone="11911112222"), headers=a.recepcao)
    await client.post("/consultas", json=payload_agendamento(b.id_medico, telefone="11933334444"), headers=b.recepcao)

    por_nome = (await client.get("/clinicas/me/tutores", params={"q": "maria"}, headers=a.recepcao)).json()
    assert len(por_nome) == 1 and por_nome[0]["telefone"] == "11911112222"
    assert por_nome[0]["pets"][0]["nome"] == "Bolinha"

    por_telefone = (await client.get("/clinicas/me/tutores", params={"q": "(11) 91111"}, headers=a.recepcao)).json()
    assert len(por_telefone) == 1

    # RN-004: a Clínica A nunca enxerga o tutor da Clínica B
    assert (await client.get("/clinicas/me/tutores", params={"q": "33334444"}, headers=a.recepcao)).json() == []


async def test_busca_de_tutores_restrita_a_recepcao_e_gestor(client, montar_clinica):
    a = await montar_clinica()
    assert (await client.get("/clinicas/me/tutores", headers=a.medico)).status_code == 403
    assert (await client.get("/clinicas/me/tutores", headers=a.gestor)).status_code == 200
    assert (await client.get("/clinicas/me/tutores")).status_code == 401


# ================================ Login 1-click da demonstração ================================

async def test_login_demo_desligado_por_padrao(client):
    original = settings.demo_login_habilitado
    settings.demo_login_habilitado = False
    try:
        assert (await client.post("/auth/demo/recepcao")).status_code == 404
    finally:
        settings.demo_login_habilitado = original


async def test_login_demo_habilitado_autentica_cada_papel_e_nunca_em_producao(client):
    await _seed.seed_demo(gravar_credenciais=False)
    original, ambiente = settings.demo_login_habilitado, settings.ambiente
    settings.demo_login_habilitado = True
    try:
        for papel in ("recepcao", "medico", "gestor"):
            r = await client.post(f"/auth/demo/{papel}")
            assert r.status_code == 200, r.text
            sessao = r.json()
            assert sessao["usuario"]["papel"] == papel
            assert sessao["clinica"]["segmento"] == "veterinaria"
            me = await client.get("/auth/me", headers={"Authorization": f"Bearer {sessao['access_token']}"})
            assert me.status_code == 200 and me.json()["papel"] == papel

        assert (await client.post("/auth/demo/superusuario")).status_code == 404   # papel desconhecido

        settings.ambiente = "producao"                                             # produção: sempre 404
        assert (await client.post("/auth/demo/gestor")).status_code == 404
    finally:
        settings.demo_login_habilitado, settings.ambiente = original, ambiente


# ================================ Seed veterinário ================================

async def test_seed_demo_e_idempotente_e_cobre_todos_os_estados(client):
    await _seed.seed_demo(gravar_credenciais=False)
    await _seed.seed_demo(gravar_credenciais=False)   # 2ª execução não duplica nada

    async with AsyncSessionLocal() as db:
        n_usuarios = await db.scalar(select(func.count(Usuario.id_usuario)))
        status = {s for (s,) in (await db.execute(select(Consulta.status).distinct())).all()}
        n_consultas = await db.scalar(select(func.count(Consulta.id_consulta)))
    assert n_usuarios == 3
    assert {"agendada", "em_andamento", "finalizada"} <= status
    assert n_consultas == 8 + 18   # hoje + histórico

    original, settings.demo_login_habilitado = settings.demo_login_habilitado, True
    try:
        gestor = (await client.post("/auth/demo/gestor")).json()
        h = {"Authorization": f"Bearer {gestor['access_token']}"}
        roi = (await client.get("/dashboard/roi", headers=h)).json()
        recepcao = (await client.post("/auth/demo/recepcao")).json()
        fila = (await client.get("/consultas/fila", headers={"Authorization": f"Bearer {recepcao['access_token']}"})).json()
    finally:
        settings.demo_login_habilitado = original

    assert roi["consultas_finalizadas"] >= 15 and roi["minutos_economizados"] > 0
    assert roi["urgencias_detectadas"] >= 2
    assert 0 < roi["taxa_adesao_pct"] < 100          # histórico inclui consultas sem triagem
    assert gestor["clinica"]["nome_fantasia"] == "Hospital Veterinário Vida Pet 24h"
    # RN-001: emergências no topo da fila e com cor vermelha
    assert fila[0]["urgencia"] is True and fila[0]["cor_prioridade"] == "VERMELHO"
    assert any(i["status_triagem"] == "pendente" for i in fila)


# =====================================================================================================
# RN-001 v2.0 — Protocolo Completo de Emergência, Logística de Resgate e Anti-Ancoragem (Migração 004)
# =====================================================================================================

from datetime import datetime, timedelta, timezone  # noqa: E402

from sqlalchemy import text, update  # noqa: E402

from app.models import Clinica, Sintoma  # noqa: E402
from app.services import ai_service, emergencia, guardrails, links  # noqa: E402
from app.services.ai_schemas import (  # noqa: E402
    AVISO_GOVERNANCA_ETICA,
    BriefingIA,
    CorPrioridade,
    NivelPrioridade,
)

SINTOMAS_V2 = {
    "Suspeita de Envenenamento / Ingestão de Tóxicos": "INTOXICACAO",
    "Atropelamento / Trauma Agudo / Queda de Altura": "TRAUMA",
    "Engasgo Ativo / Asfixia / Língua Roxa ou Azulada (Cianose)": "DISPNEIA",
    "Hemorragia Intensa / Sangramento que não estanca": "HEMORRAGIA",
}


async def _agendar(client, a, telefone="11955554444", pet="Rex"):
    r = await client.post("/consultas", headers=a.recepcao, json=payload_agendamento(a.id_medico, telefone, pet))
    assert r.status_code == 201, r.text
    item = r.json()
    return item, item["link_triagem"].rsplit("/", 1)[1]


# ---------------------------------- Migração 004 ----------------------------------

async def test_migracao_004_cria_colunas_com_tipos_e_defaults_corretos(client, montar_clinica):
    async with AsyncSessionLocal() as db:
        versao = await db.scalar(text("SELECT version_num FROM alembic_version"))
        cols = (await db.execute(text(
            "SELECT table_name, column_name, data_type, is_nullable, character_maximum_length "
            "FROM information_schema.columns WHERE table_name IN ('clinica','consulta','formulario_triagem')"
        ))).all()
    assert versao == "004_protocolo_emergencia_resgate"
    c = {(t, n): (tipo, nulo, tam) for t, n, tipo, nulo, tam in cols}
    esperado = {
        ("clinica", "atendimento_24h"): ("boolean", "NO", None),
        ("clinica", "horario_fechamento"): ("character varying", "NO", 10),
        ("clinica", "possui_veiculo_resgate"): ("boolean", "NO", None),
        ("clinica", "telefone_emergencia"): ("character varying", "YES", 20),
        ("clinica", "endereco_completo"): ("character varying", "YES", 300),
        ("consulta", "modalidade_emergencia"): ("character varying", "YES", 40),
        ("consulta", "localizacao_gps_tutor"): ("character varying", "YES", 255),
        ("formulario_triagem", "alerta_critico_exibido_em"): ("timestamp with time zone", "YES", None),
        ("formulario_triagem", "ciente_risco_morte"): ("boolean", "NO", None),
    }
    for chave, valor in esperado.items():
        assert c.get(chave) == valor, f"{chave}: {c.get(chave)} != {valor}"

    # defaults seguros para clínicas criadas pelo onboarding (24h, 18:00, com veículo)
    a = await montar_clinica()
    async with AsyncSessionLocal() as db:
        cl = await db.get(Clinica, a.id_clinica)
    assert cl.atendimento_24h is True and cl.horario_fechamento == "18:00"
    assert cl.possui_veiculo_resgate is True and cl.telefone_emergencia is None


async def test_catalogo_v2_tem_os_4_sinais_explicitos_de_emergencia_e_migra_nomes_antigos(client):
    async with AsyncSessionLocal() as db:
        todos = {s.nome_sintoma: s for s in (await db.execute(select(Sintoma))).scalars()}
    for parte, categoria in SINTOMAS_V2.items():
        s = next(v for k, v in todos.items() if k.startswith(parte))
        assert s.alerta_urgencia is True and s.categoria == "Emergência"
        assert guardrails.classificar_emergencia(s.nome_sintoma) == categoria
    nome_veneno = next(k for k in todos if k.startswith("Suspeita de Envenenamento"))
    for palavra in ("chumbinho", "veneno de rato", "plantas", "sapo", "chocolate", "remédio humano"):
        assert palavra in nome_veneno

    # banco legado: o nome antigo é renomeado NO LUGAR (sem duplicar) ao rodar o seed novamente
    async with AsyncSessionLocal() as db:
        s = await db.scalar(select(Sintoma).where(Sintoma.nome_sintoma == _seed.S_TRAUMA))
        id_antes = s.id_sintoma
        s.nome_sintoma = "Atropelamento, queda de altura ou trauma grave"
        await db.commit()
    await _seed.seed_sintomas()
    async with AsyncSessionLocal() as db:
        nomes = [n for (n,) in (await db.execute(select(Sintoma.nome_sintoma))).all()]
        s = await db.scalar(select(Sintoma).where(Sintoma.nome_sintoma == _seed.S_TRAUMA))
    assert s.id_sintoma == id_antes
    assert "Atropelamento, queda de altura ou trauma grave" not in nomes


async def test_seed_clinica_demo_tem_protocolo_de_emergencia_e_casos_no_topo_da_fila(client):
    await _seed.seed_demo(gravar_credenciais=False)
    async with AsyncSessionLocal() as db:
        cl = await db.scalar(select(Clinica).where(Clinica.cnpj == _seed.CNPJ_DEMO))
    assert cl.nome_fantasia == "Hospital Veterinário Vida Pet 24h"
    assert cl.atendimento_24h and cl.possui_veiculo_resgate
    assert cl.telefone_emergencia == "5562999990000" and "Anápolis" in cl.endereco_completo

    original, settings.demo_login_habilitado = settings.demo_login_habilitado, True
    try:
        rec = (await client.post("/auth/demo/recepcao")).json()
        fila = (await client.get("/consultas/fila", headers={"Authorization": f"Bearer {rec['access_token']}"})).json()
    finally:
        settings.demo_login_habilitado = original
    topo = [i["modalidade_emergencia"] for i in fila[:2]]
    assert sorted(topo) == ["EMERGENCIA_A_CAMINHO", "RESGATE_SOLICITADO"]
    resgate = next(i for i in fila if i["modalidade_emergencia"] == "RESGATE_SOLICITADO")
    assert resgate["maps_url_tutor"].startswith("https://www.google.com/maps/") and resgate["ciente_risco_morte"]


# ---------------------------------- Guardrails (antídotos / primeiros socorros negativos) ----------------------------------

def _briefing_com(**campos) -> BriefingIA:
    base = dict(
        flag_urgencia_detectada=True, nivel_prioridade=NivelPrioridade.EMERGENCIA,
        cor_prioridade=CorPrioridade.VERMELHO,
        resumo_estruturado="Síntese descritiva dos sinais relatados.",
        traducao_semiologica=[], cronologia_evolucao="Início há 1 hora.",
        alerta_medicacao_e_bioindicadores="Nenhuma medicação informada.",
        sinais_alerta_identificados=["Suspeita Leiga Relatada (A Confirmar)"],
        pontos_investigacao=["Avaliar vias aéreas e padrão respiratório.", "Aferir TPC e mucosas.", "Aferir glicemia."],
        orientacao_preparatoria_consultorio="Preparar o Box de Emergência e realizar o exame ABC.",
        alerta_seguranca_tutor="Leve seu animal imediatamente ao atendimento.",
        aviso_governanca_etica=AVISO_GOVERNANCA_ETICA,
    )
    base.update(campos)
    return BriefingIA(**base)


def test_briefing_anti_ancoragem_aprovado_pelo_guardrail():
    assert guardrails.verificar_violacoes_eticas(_briefing_com()) == []


import pytest  # noqa: E402


@pytest.mark.parametrize("texto", [
    "Considerar atropina na chegada.",
    "Fazer carvão ativado imediatamente.",
    "Aplicar Vitamina K1 conforme necessário.",
    "Realizar lavagem gástrica.",
    "Orientar a induzir vômito em casa.",
    "O tutor deve provocar vômito no animal.",
    "Administrar apomorfina para esvaziar o estômago.",
    "Usar água oxigenada para fazer vomitar.",
])
def test_guardrail_bloqueia_antidotos_e_condutas_invasivas(texto):
    for campo in ("orientacao_preparatoria_consultorio", "resumo_estruturado", "alerta_seguranca_tutor"):
        v = guardrails.verificar_violacoes_eticas(_briefing_com(**{campo: texto}))
        assert any("antídoto" in x for x in v), (campo, texto, v)
    v = guardrails.verificar_violacoes_eticas(_briefing_com(pontos_investigacao=[texto, "b", "c"]))
    assert any("antídoto" in x for x in v)


def test_guardrail_permite_registrar_o_que_o_tutor_ja_administrou():
    # Dado informado pelo tutor (medicação já dada em casa) é essencial ao médico — não é recomendação da IA.
    b = _briefing_com(alerta_medicacao_e_bioindicadores="Tutor informa ter dado água oxigenada há 20 minutos.")
    assert guardrails.verificar_violacoes_eticas(b) == []


def test_primeiros_socorros_negativos_textos_exatos_e_fallback():
    n = guardrails.PRIMEIROS_SOCORROS_NEGATIVOS
    assert n["INTOXICACAO"] == (
        "PROIBIDO dar leite, azeite, água ou remédios caseiros. NÃO provoque vômito (risco de asfixia e "
        "queimadura esofágica). Se possível, leve a embalagem ou foto do agente suspeito.")
    assert n["NEUROLOGICO"] == (
        "NÃO coloque a mão na boca do animal (ele não engole a língua). Afaste objetos ao redor, proteja a "
        "cabeça com um pano macio e desloque-se imediatamente.")
    assert n["DISPNEIA"] == (
        "Mantenha o animal em local fresco, retire coleiras apertadas e evite comprimir o tórax ou forçá-lo "
        "a deitar.")
    assert set(guardrails.primeiros_socorros_para(["INTOXICACAO", "INTOXICACAO", None, "NEUROLOGICO"])) == {
        "INTOXICACAO", "NEUROLOGICO"}
    assert list(guardrails.primeiros_socorros_para([None, "xyz"])) == ["GERAL"]


@pytest.mark.parametrize("relato,esperado", [
    ("acho que ele comeu veneno de rato", ["veneno"]),
    ("comeu CHUMBINHO ontem", ["chumbinho"]),
    ("foi atropelado agora", ["atropelado"]),
    ("está sangrando muito na pata", ["sangrando muito"]),
    ("teve uma convulsão", ["convulsão"]),
    ("ele não respira direito", ["não respira"]),
    ("a língua está roxa", ["língua roxa"]),
    ("Língua ROXA e engasgado", ["língua roxa", "engasgo"]),
])
def test_termos_criticos_no_relato_livre(relato, esperado):
    assert guardrails.detectar_termos_criticos(relato) == esperado


def test_relato_comum_nao_dispara_o_disjuntor():
    assert guardrails.detectar_termos_criticos("Ele vomitou espuma amarela duas vezes e está quieto.") == []
    assert guardrails.classificar_emergencia("Vômito") is None


def test_system_prompt_contem_protocolo_anti_ancoragem_e_proibicao_de_antidotos():
    p = ai_service.SYSTEM_PROMPT
    assert "PROTOCOLO DE DESCARTE DIFERENCIAL ANTI-ANCORAGEM" in p
    assert "Suspeita Leiga Relatada (A Confirmar)" in p
    assert "PRESENCIADA" in p and "SUPOSTA" in p
    for item in ("Vias Aéreas", "Padrão Respiratório", "TPC/Mucosas", "Pulso", "Temperatura", "Glicemia",
                 "Box de Emergência", "oxigênio", "acesso venoso"):
        assert item in p
    for proibido in ("atropina", "carvão ativado", "vitamina K1", "lavagem gástrica", "apomorfina",
                     "água oxigenada"):
        assert proibido in p   # citados APENAS como lista de proibições


def test_prompt_do_usuario_inclui_emergencia_acionada():
    dados = ai_service.DadosTriagem(
        especie="Cão", raca="SRD", sexo="Macho", idade_texto="3 anos", ambiente="Casa", alimentacao="Ração",
        vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=False,
        medicamento_continuo="Nenhum", aspecto_urina_fezes="n", alteracao_peso_apetite="n",
        ingestao_hidrica="n", tempo_evolucao="1 h", relato_livre_tutor="comeu veneno",
        sintomas_marcados=[], emergencia_acionada="RESGATE_SOLICITADO")
    assert "RESGATE_SOLICITADO" in ai_service.montar_prompt_usuario(dados, False)


# ---------------------------------- Horário da clínica ----------------------------------

def test_clinica_aberta_agora_respeita_24h_e_horario_de_fechamento():
    sp = timezone(timedelta(hours=-3))
    def em(h, m=0):
        return datetime(2026, 11, 9, h, m, tzinfo=sp).astimezone(timezone.utc)
    c24 = Clinica(atendimento_24h=True, horario_fechamento="18:00")
    assert emergencia.clinica_aberta_agora(c24, em(3)) is True
    c = Clinica(atendimento_24h=False, horario_fechamento="18:00")
    assert emergencia.clinica_aberta_agora(c, em(10)) is True
    assert emergencia.clinica_aberta_agora(c, em(17, 59)) is True
    assert emergencia.clinica_aberta_agora(c, em(18, 0)) is False
    assert emergencia.clinica_aberta_agora(c, em(3)) is False
    assert emergencia.clinica_aberta_agora(Clinica(atendimento_24h=False, horario_fechamento="lixo"), em(19)) is False


def test_timestamp_do_alerta_so_e_aceito_se_plausivel():
    agora = datetime.now(timezone.utc)
    ok = agora - timedelta(minutes=2)
    assert emergencia.instante_alerta_confiavel(ok) == ok
    futuro = emergencia.instante_alerta_confiavel(agora + timedelta(days=1))
    antigo = emergencia.instante_alerta_confiavel(agora - timedelta(days=3))
    assert abs((futuro - agora).total_seconds()) < 5 and abs((antigo - agora).total_seconds()) < 5


def test_links_de_gps_maps_e_whatsapp_de_resgate():
    assert links.coordenadas("-16.3281, -48.9534") == (-16.3281, -48.9534)
    assert links.coordenadas("999,999") is None and links.coordenadas("Rua A, 10") is None
    assert links.maps_url_localizacao("-16.3281,-48.9534").endswith("query=-16.3281,-48.9534")
    assert "Rua%20das%20Flores" in links.maps_url_localizacao("Rua das Flores, 10")
    wa = links.whatsapp_resgate_url(
        telefone_emergencia="62999990000", clinica_nome="Vida Pet", tutor_nome="Ana", pet_nome="Rex",
        maps_url="https://www.google.com/maps/search/?api=1&query=-16.3,-48.9")
    assert wa.startswith("https://wa.me/5562999990000?text=") and "maps" in wa
    assert links.whatsapp_resgate_url(telefone_emergencia=None, clinica_nome="x", tutor_nome="y",
                                      pet_nome="z", maps_url=None) is None


# ---------------------------------- Rota de acionamento de emergência ----------------------------------

async def test_contexto_publico_traz_protocolo_da_clinica_e_categoria_dos_sintomas(client, montar_clinica):
    a = await montar_clinica()
    async with AsyncSessionLocal() as db:
        await db.execute(update(Clinica).where(Clinica.id_clinica == a.id_clinica).values(
            telefone_emergencia="62999990000", endereco_completo="Rua 1, Anápolis-GO"))
        await db.commit()
    _, token = await _agendar(client, a)
    ctx = (await client.get(f"/publico/triagem/{token}")).json()
    e = ctx["emergencia"]
    assert e["atendimento_24h"] and e["clinica_aberta_agora"] and e["possui_veiculo_resgate"]
    assert e["whatsapp_plantao"] == "62999990000"
    assert e["url_hospital_24h"] == "https://www.google.com/maps/search/Hospital+Veterinario+24h/"
    assert {"INTOXICACAO", "NEUROLOGICO", "DISPNEIA"} <= set(e["primeiros_socorros_negativos"])
    assert any(g["categoria"] == "INTOXICACAO" and g["termo"] == "veneno" for g in e["gatilhos_texto"])
    por_nome = {s["nome_sintoma"]: s for s in ctx["sintomas"]}
    assert por_nome[_seed.S_ENVENENAMENTO]["categoria_emergencia"] == "INTOXICACAO"
    assert por_nome[_seed.S_TRAUMA]["categoria_emergencia"] == "TRAUMA"
    assert por_nome["Vômito"]["categoria_emergencia"] is None


async def test_estou_a_caminho_registra_modalidade_e_vai_ao_topo_da_fila(client, montar_clinica):
    a = await montar_clinica()
    primeiro, _ = await _agendar(client, a, "11955550001", "Primeiro")
    segundo, token2 = await _agendar(client, a, "11955550002", "Segundo")

    r = await client.post(f"/publico/triagem/{token2}/acionar-emergencia", json={
        "modalidade": "EMERGENCIA_A_CAMINHO", "ciente_risco_morte": True,
        "categorias_emergencia": ["INTOXICACAO"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["modalidade_emergencia"] == "EMERGENCIA_A_CAMINHO" and out["whatsapp_resgate_url"] is None
    assert "google.com/maps/dir" in out["rota_clinica"]["google_maps"] and "waze.com" in out["rota_clinica"]["waze"]
    assert list(out["primeiros_socorros_negativos"]) == ["INTOXICACAO"]

    for headers in (a.recepcao, a.medico):   # topo da fila da recepção E do médico
        fila = (await client.get("/consultas/fila", headers=headers)).json()
        assert fila[0]["id_consulta"] == segundo["id_consulta"]
        assert fila[0]["modalidade_emergencia"] == "EMERGENCIA_A_CAMINHO"
        assert fila[0]["urgencia"] is True and fila[0]["status_triagem"] == "urgencia"
        assert fila[0]["cor_prioridade"] == "VERMELHO"
        assert fila[1]["id_consulta"] == primeiro["id_consulta"] and fila[1]["modalidade_emergencia"] is None

    b = (await client.get(f"/triagem/{segundo['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["urgencia"] is True and b["modalidade_emergencia"] == "EMERGENCIA_A_CAMINHO"
    assert len(b["protocolo_abc_emergencia"]) >= 5
    assert any("Vias aéreas" in x for x in b["protocolo_abc_emergencia"])
    assert any("Box de Emergência" in x for x in b["protocolo_abc_emergencia"])


async def test_resgate_solicitado_gera_whatsapp_com_google_maps_e_grava_gps(client, montar_clinica):
    a = await montar_clinica()
    async with AsyncSessionLocal() as db:
        await db.execute(update(Clinica).where(Clinica.id_clinica == a.id_clinica).values(
            telefone_emergencia="62999990000"))
        await db.commit()
    item, token = await _agendar(client, a)
    r = await client.post(f"/publico/triagem/{token}/acionar-emergencia", json={
        "modalidade": "RESGATE_SOLICITADO", "localizacao_gps_tutor": "-16.3281,-48.9534"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["localizacao_gps_tutor"] == "-16.3281,-48.9534"
    assert out["maps_url_tutor"] == "https://www.google.com/maps/search/?api=1&query=-16.3281,-48.9534"
    assert out["whatsapp_resgate_url"].startswith("https://wa.me/5562999990000?text=")
    assert "google.com/maps" in out["whatsapp_resgate_url"] and "-16.3281" in out["whatsapp_resgate_url"]

    fila = (await client.get("/consultas/fila", headers=a.recepcao)).json()
    assert fila[0]["modalidade_emergencia"] == "RESGATE_SOLICITADO"
    assert fila[0]["localizacao_gps_tutor"] == "-16.3281,-48.9534" and fila[0]["maps_url_tutor"]

    # o resgate nunca é rebaixado por um clique posterior em "Estou a caminho"
    r2 = await client.post(f"/publico/triagem/{token}/acionar-emergencia", json={"modalidade": "EMERGENCIA_A_CAMINHO"})
    assert r2.status_code == 200 and r2.json()["modalidade_emergencia"] == "RESGATE_SOLICITADO"


async def test_resgate_exige_localizacao_e_clinica_com_veiculo(client, montar_clinica):
    a = await montar_clinica()
    _, token = await _agendar(client, a)
    url = f"/publico/triagem/{token}/acionar-emergencia"
    assert (await client.post(url, json={"modalidade": "RESGATE_SOLICITADO"})).status_code == 422
    assert (await client.post(url, json={"modalidade": "RESGATE_SOLICITADO", "localizacao_gps_tutor": "  "})).status_code == 422
    assert (await client.post(url, json={"modalidade": "TELEPORTE"})).status_code == 422

    async with AsyncSessionLocal() as db:
        await db.execute(update(Clinica).where(Clinica.id_clinica == a.id_clinica).values(possui_veiculo_resgate=False))
        await db.commit()
    r = await client.post(url, json={"modalidade": "RESGATE_SOLICITADO", "localizacao_gps_tutor": "Rua das Flores, 10"})
    assert r.status_code == 422 and "veículo" in r.json()["detail"]
    # sem veículo, "Estou a caminho" continua funcionando
    assert (await client.post(url, json={"modalidade": "EMERGENCIA_A_CAMINHO"})).status_code == 200


async def test_acionar_emergencia_token_invalido_cancelada_e_idempotente(client, montar_clinica):
    a = await montar_clinica()
    assert (await client.post("/publico/triagem/" + "x" * 40 + "/acionar-emergencia",
                              json={"modalidade": "EMERGENCIA_A_CAMINHO"})).status_code == 404
    item, token = await _agendar(client, a)
    url = f"/publico/triagem/{token}/acionar-emergencia"
    assert (await client.post(url, json={"modalidade": "EMERGENCIA_A_CAMINHO"})).status_code == 200
    assert (await client.post(url, json={"modalidade": "EMERGENCIA_A_CAMINHO"})).status_code == 200  # duplo clique
    await client.patch(f"/consultas/{item['id_consulta']}/cancelar", headers=a.recepcao)
    assert (await client.post(url, json={"modalidade": "EMERGENCIA_A_CAMINHO"})).status_code == 422


async def test_acionar_emergencia_apos_triagem_grava_auditoria_juridica(client, montar_clinica, ia):
    a = await montar_clinica()
    item, token = await _agendar(client, a)
    assert (await client.post(f"/publico/triagem/{token}", json=payload_triagem())).status_code == 201
    exibido = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = await client.post(f"/publico/triagem/{token}/acionar-emergencia", json={
        "modalidade": "EMERGENCIA_A_CAMINHO", "ciente_risco_morte": True, "alerta_critico_exibido_em": exibido})
    assert r.status_code == 200
    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["ciente_risco_morte"] is True and b["alerta_critico_exibido_em"] is not None
    assert b["urgencia"] is True and b["modalidade_emergencia"] == "EMERGENCIA_A_CAMINHO"


# ---------------------------------- Submissão: gatilho de texto e auditoria ----------------------------------

async def test_termo_critico_no_relato_ativa_urgencia_deterministica_e_primeiros_socorros(client, montar_clinica, ia):
    a = await montar_clinica()
    item, token = await _agendar(client, a)
    r = await client.post(f"/publico/triagem/{token}", json=payload_triagem(
        relato_livre_tutor="Acho que ele comeu chumbinho, está babando e tremendo."))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["urgencia_detectada"] is True and out["acao_recomendada"] == "PRONTO_SOCORRO_IMEDIATO"
    assert out["termos_criticos_relato"] == ["chumbinho"]
    assert "PROIBIDO dar leite" in out["primeiros_socorros_negativos"]["INTOXICACAO"]
    # a IA recebe o gatilho e o relatório nunca é rebaixado
    assert any("chumbinho" in s for s in ia.chamadas[0].sintomas_urgencia)
    fila = (await client.get("/consultas/fila", headers=a.recepcao)).json()
    assert fila[0]["urgencia"] is True and fila[0]["cor_prioridade"] == "VERMELHO"
    res = (await client.get(f"/publico/triagem/{token}/resultado")).json()
    assert res["urgencia_detectada"] is True and "INTOXICACAO" in res["primeiros_socorros_negativos"]


async def test_submissao_com_sintoma_de_envenenamento_retorna_card_negativo_e_audita_ciencia(client, montar_clinica, ia):
    a = await montar_clinica()
    item, token = await _agendar(client, a)
    sid = await id_sintoma("Envenenamento")
    exibido = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    r = await client.post(f"/publico/triagem/{token}", json=payload_triagem(
        [sid], ciente_risco_morte=True, alerta_critico_exibido_em=exibido,
        modalidade_emergencia="RESGATE_SOLICITADO", localizacao_gps_tutor="-16.33,-48.95"))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["urgencia_detectada"] and list(out["primeiros_socorros_negativos"]) == ["INTOXICACAO"]
    assert out["modalidade_emergencia"] == "RESGATE_SOLICITADO" and out["maps_url_tutor"]
    assert ia.chamadas[0].emergencia_acionada == "RESGATE_SOLICITADO"

    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["ciente_risco_morte"] is True and b["alerta_critico_exibido_em"] is not None
    assert b["modalidade_emergencia"] == "RESGATE_SOLICITADO" and b["localizacao_gps_tutor"] == "-16.33,-48.95"
    assert b["formulario"]["urgencia_deterministica"] is True


async def test_submissao_normal_nao_tem_emergencia_nem_auditoria(client, montar_clinica, ia):
    a = await montar_clinica()
    item, token = await _agendar(client, a)
    out = (await client.post(f"/publico/triagem/{token}", json=payload_triagem())).json()
    assert out["urgencia_detectada"] is False and out["primeiros_socorros_negativos"] == {}
    b = (await client.get(f"/triagem/{item['id_consulta']}/briefing", headers=a.medico)).json()
    assert b["ciente_risco_morte"] is False and b["alerta_critico_exibido_em"] is None
    assert b["modalidade_emergencia"] is None and b["protocolo_abc_emergencia"] == []


# ---------------------------------- Dashboard executivo ----------------------------------

async def test_dashboard_metricas_roi_receita_e_distribuicao_manchester(client, montar_clinica):
    await _seed.seed_demo(gravar_credenciais=False)
    original, settings.demo_login_habilitado = settings.demo_login_habilitado, True
    try:
        g = (await client.post("/auth/demo/gestor")).json()
        h = {"Authorization": f"Bearer {g['access_token']}"}
        rec = (await client.post("/auth/demo/recepcao")).json()
        hr = {"Authorization": f"Bearer {rec['access_token']}"}
    finally:
        settings.demo_login_habilitado = original
    # período inclui o restante do dia (casos do seed agendados para os próximos minutos)
    ate = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = await client.get("/dashboard/metricas", headers=h, params={"ate": ate})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["horas_economizadas"] > 0 and m["capacidade_extra_atendimentos"] > 0
    assert m["receita_adicional_potencial"] == round(
        m["capacidade_extra_atendimentos"] * m["ticket_medio_consulta"], 2)
    assert [d["cor"] for d in m["distribuicao_risco"]] == ["VERMELHO", "LARANJA", "AMARELO", "VERDE", "AZUL"]
    assert sum(d["quantidade"] for d in m["distribuicao_risco"]) == m["triagens_realizadas"]
    assert m["distribuicao_risco"][0]["quantidade"] >= 4     # 2 emergências de hoje + urgências do histórico
    assert m["emergencias_acionadas"] == 2 and m["resgates_solicitados"] == 1
    assert 0 < m["taxa_adesao_pct"] < 100
    assert (await client.get("/dashboard/metricas", headers=hr)).status_code == 403
    assert (await client.get("/dashboard/metricas")).status_code == 401