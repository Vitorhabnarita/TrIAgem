"""
tests/conftest.py — Fixtures: banco de teste isolado, cliente HTTP ASGI, IA simulada.

O banco de teste é um PostgreSQL LOCAL descartável (nunca o Cloud SQL de produção).
"""

import os

# Configura ANTES de importar a aplicação (variáveis de ambiente têm prioridade sobre o .env)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1:54329/triagem_test"
)
os.environ["JWT_SECRET"] = "segredo-de-teste-com-mais-de-32-caracteres-ok"
os.environ["ADMIN_API_KEY"] = "admin-key-de-teste-com-24+chars"
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "") or "chave-falsa"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
import app.database  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # noqa: E402

TEST_URL = os.environ["DATABASE_URL"]
settings.database_url = TEST_URL
app.database.engine = create_async_engine(TEST_URL, pool_pre_ping=True)
app.database.AsyncSessionLocal = async_sessionmaker(
    bind=app.database.engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
engine = app.database.engine
AsyncSessionLocal = app.database.AsyncSessionLocal

from app.ratelimit import resetar_limites  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services.ai_schemas import (  # noqa: E402
    AVISO_GOVERNANCA_ETICA,
    BriefingIA,
    CorPrioridade,
    NivelPrioridade,
    TraducaoSemiologica,
)
from app.services.ai_service import DadosTriagem, IAIndisponivel, ResultadoIA  # noqa: E402
from app.services.guardrails import normalizar_briefing  # noqa: E402
from main import app  # noqa: E402

import importlib.util  # noqa: E402
import pathlib  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "seed_script", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "seed.py"
)
_seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_seed)  # type: ignore[union-attr]

ADMIN = {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}


@pytest_asyncio.fixture(autouse=True)
async def banco_limpo(request):
    """Zera dados antes de cada teste de integração e recarrega o catálogo de sintomas."""
    resetar_limites()
    if "test_unitarios" in request.node.nodeid:
        yield
        return

    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE relatorio_ia, formulario_sintoma, formulario_triagem, consulta, pet, tutor, "
            "usuario, medico_veterinario, clinica, sintoma RESTART IDENTITY CASCADE"
        ))
    await _seed.seed_sintomas()
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class IAFalsa:
    """Substitui o Gemini: determinística, sem rede. Atributos controlam o cenário."""

    def __init__(self):
        self.flag_semantico = False
        self.falhar = False
        self.chamadas: list[DadosTriagem] = []

    async def __call__(self, dados: DadosTriagem) -> ResultadoIA:
        self.chamadas.append(dados)
        if self.falhar:
            raise IAIndisponivel("simulado")
        nivel = NivelPrioridade.EMERGENCIA if self.flag_semantico else NivelPrioridade.POUCO_URGENTE
        b = BriefingIA(
            flag_urgencia_detectada=self.flag_semantico,
            nivel_prioridade=nivel,
            cor_prioridade=CorPrioridade.AZUL,
            resumo_estruturado="Síntese descritiva simulada.",
            traducao_semiologica=[
                TraducaoSemiologica(relato_leigo="vomitou amarelo", termo_tecnico_descritivo="êmese bilioso")
            ],
            cronologia_evolucao="Início há 2 dias.",
            alerta_medicacao_e_bioindicadores=f"Medicação informada: {dados.medicamento_continuo}.",
            sinais_alerta_identificados=[],
            pontos_investigacao=["a", "b", "c"],
            orientacao_preparatoria_consultorio="Realizar exame físico completo.",
            alerta_seguranca_tutor="Não medique seu animal por conta própria.",
            aviso_governanca_etica=AVISO_GOVERNANCA_ETICA,
        )
        return ResultadoIA(
            briefing=normalizar_briefing(b, dados.urgencia_deterministica), modelo="ia-falsa"
        )


@pytest.fixture
def ia(monkeypatch) -> IAFalsa:
    fake = IAFalsa()
    monkeypatch.setattr(ai_service, "gerar_briefing", fake)
    return fake


# ---------------------------------------------------------------------------
# Fábrica de cenário: clínica + médico + usuários logados
# ---------------------------------------------------------------------------

class Cenario:
    def __init__(self):
        self.id_clinica = 0
        self.id_medico = 0
        self.recepcao: dict = {}
        self.medico: dict = {}
        self.gestor: dict = {}


async def _login(client, email, senha) -> dict:
    r = await client.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def montar_clinica(client):
    contador = {"n": 0}

    async def _montar(nome="Clínica A") -> Cenario:
        contador["n"] += 1
        n = contador["n"]
        cnpj = f"{n:02d}.345.678/0001-9{n % 10}"
        r = await client.post("/admin/clinicas", json={"nome_fantasia": nome, "cnpj": cnpj}, headers=ADMIN)
        assert r.status_code == 201, r.text
        c = Cenario()
        c.id_clinica = r.json()["id_clinica"]
        r = await client.post(
            f"/admin/clinicas/{c.id_clinica}/medicos",
            json={"nome": f"Dr. Teste {n}", "crmv": f"CRMV-SP {1000 + n}"}, headers=ADMIN,
        )
        assert r.status_code == 201, r.text
        c.id_medico = r.json()["id_medico"]
        senha = "SenhaForte#12345"
        for papel, extra in (("recepcao", {}), ("medico", {"id_medico": c.id_medico}), ("gestor", {})):
            r = await client.post(
                f"/admin/clinicas/{c.id_clinica}/usuarios",
                json={"nome": papel, "email": f"{papel}{n}@teste.com", "senha": senha, "papel": papel, **extra},
                headers=ADMIN,
            )
            assert r.status_code == 201, r.text
            setattr(c, papel, await _login(client, f"{papel}{n}@teste.com", senha))
        return c

    return _montar


def payload_agendamento(id_medico: int, telefone="11999998888", pet="Bolinha") -> dict:
    return {
        "id_medico": id_medico,
        "tutor": {"nome": "Maria Oliveira", "telefone": telefone},
        "pet": {"nome": pet, "especie": "Cão", "raca": "SRD", "sexo": "Macho", "idade_texto": "3 anos"},
    }


def payload_triagem(sintoma_ids=None, **over) -> dict:
    base = {
        "aceite_termo": True,
        "ambiente": "Apartamento",
        "alimentacao": "Ração premium",
        "vacinacao_em_dia": True,
        "vermifugo_em_dia": True,
        "convivio_outros_animais": False,
        "medicamento_continuo": "Nenhum",
        "aspecto_urina_fezes": "Fezes pastosas, urina normal",
        "alteracao_peso_apetite": "Come menos há 2 dias",
        "ingestao_hidrica": "Bebe normalmente",
        "tempo_evolucao": "2 dias",
        "relato_livre_tutor": "Ele vomitou espuma amarela duas vezes e está quieto.",
        "sintoma_ids": sintoma_ids or [],
    }
    base.update(over)
    return base


async def id_sintoma(nome_parcial: str) -> int:
    from sqlalchemy import select  # noqa: PLC0415
    from app.models import Sintoma  # noqa: PLC0415
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Sintoma).where(Sintoma.nome_sintoma.ilike(f"%{nome_parcial}%")))
        return res.scalars().first().id_sintoma
