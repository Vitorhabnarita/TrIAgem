"""Testa quais modelos Gemini respondem para a chave atual, e inspeciona (mascarado) a DATABASE_URL."""

import asyncio
import os
import re
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import settings  # noqa: E402


def inspecionar_url() -> None:
    url = settings.database_url
    m = re.match(r"^(?P<esq>[^:]+)://(?P<user>[^:@/]*):(?P<pw>.*)@(?P<resto>[^@]*)$", url)
    if not m:
        print("[URL] formato não reconhecido")
        return
    pw = m.group("pw")
    print("[URL] driver:", m.group("esq"))
    print("[URL] user:", m.group("user"))
    print("[URL] host/db:", m.group("resto"))
    print("[URL] senha: tamanho=%d, url-encoded=%s, caracteres crus perigosos=%s" % (
        len(pw), "%" in pw, [c for c in "/?#@:" if c in pw]))
    print("[URL] senha decodificada tem tamanho:", len(unquote(pw)))


async def testar_modelos() -> None:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    candidatos = [
        "gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite",
        "gemini-3-flash-preview", "gemini-3.8-flash", "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
    ]
    for nome in candidatos:
        try:
            r = await client.aio.models.generate_content(
                model=nome,
                contents='Retorne JSON {"ok": true}',
                config=types.GenerateContentConfig(
                    temperature=0.1, response_mime_type="application/json"
                ),
            )
            print(f"[GEMINI] {nome}: OK -> {(r.text or '').strip()[:40]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[GEMINI] {nome}: ERRO {str(e)[:110]}")


inspecionar_url()
asyncio.run(testar_modelos())

