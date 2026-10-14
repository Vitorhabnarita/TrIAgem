"""Diagnóstico de ambiente: Cloud SQL + Gemini. Nunca imprime segredos."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402


async def testar_db() -> None:
    u = make_url(settings.database_url)
    print(f"[DB] host={u.host} db={u.database}")
    try:
        c = await asyncpg.connect(
            user=u.username, password=u.password, host=u.host,
            port=u.port, database=u.database, timeout=20,
        )
    except Exception as e:  # noqa: BLE001
        print("[DB] FALHA:", type(e).__name__, str(e)[:200])
        return
    rows = await c.fetch("select tablename from pg_tables where schemaname='public' order by 1")
    print("[DB] tabelas:", [r[0] for r in rows])
    try:
        print("[DB] alembic:", await c.fetchval("select version_num from alembic_version"))
        print("[DB] sintomas cadastrados:", await c.fetchval("select count(*) from sintoma"))
    except Exception as e:  # noqa: BLE001
        print("[DB] aviso:", e)
    await c.close()


async def testar_gemini() -> None:
    key = os.environ.get("GEMINI_API_KEY") or _ler_env("GEMINI_API_KEY")
    modelo = os.environ.get("GEMINI_MODEL") or _ler_env("GEMINI_MODEL")
    print(f"[GEMINI] chave presente={bool(key)} modelo_configurado={modelo!r}")
    if not key:
        return
    from google import genai

    client = genai.Client(api_key=key)
    try:
        nomes = []
        async for m in await client.aio.models.list():
            nomes.append(m.name.replace("models/", ""))
        flash = sorted(n for n in nomes if "flash" in n and "gemini" in n)
        print("[GEMINI] modelos flash disponíveis:", flash[:25])
    except Exception as e:  # noqa: BLE001
        print("[GEMINI] erro listando modelos:", type(e).__name__, str(e)[:200])
    for candidato in [modelo, "gemini-2.5-flash"]:
        if not candidato:
            continue
        try:
            r = await client.aio.models.generate_content(
                model=candidato, contents="Responda apenas: ok"
            )
            print(f"[GEMINI] {candidato}: OK -> {r.text.strip()[:30]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[GEMINI] {candidato}: ERRO {type(e).__name__}: {str(e)[:160]}")


def _ler_env(nome: str) -> str | None:
    try:
        for linha in open(os.path.join(os.path.dirname(__file__), "..", ".env"), encoding="utf-8"):
            if linha.strip().startswith(nome + "="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


async def main() -> None:
    await testar_db()
    await testar_gemini()


asyncio.run(main())

