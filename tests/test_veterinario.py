"""
tests/test_veterinario.py — Especialização veterinária do MVP (dados clínicos do pet, manejo preventivo,
busca de tutores para o agendamento rápido, login 1-click de demonstração e seed).

Complementa (sem alterar) as suítes de regras de negócio e unitárias.
"""

from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Consulta, Usuario
from tests.conftest import _seed, payload_agendamento, payload_triagem


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
