"""app/services/links.py — Link único da Triagem Pré-Consulta e mensagem de WhatsApp."""

import re
from urllib.parse import quote

from app.config import settings


def link_triagem(token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/t/{token}"


def _telefone_whatsapp(telefone: str) -> str:
    d = re.sub(r"\D", "", telefone)
    return d if d.startswith("55") and len(d) >= 12 else f"55{d}"


def whatsapp_url(*, token: str, tutor_nome: str, telefone: str, pet_nome: str, clinica_nome: str) -> str:
    primeiro = (tutor_nome.strip().split(" ")[0] if tutor_nome.strip() else "tutor")
    msg = (
        f"Olá, {primeiro}! Aqui é a {clinica_nome}. Para agilizar o atendimento de {pet_nome}, "
        f"preencha a Triagem Pré-Consulta pelo celular (leva cerca de 2 minutos):\n"
        f"{link_triagem(token)}\n\n"
        "Atenção: se {pet} estiver com convulsão, falta de ar, sangramento ou desmaio, "
        "não aguarde — procure atendimento de emergência imediatamente."
    ).replace("{pet}", pet_nome)
    return f"https://wa.me/{_telefone_whatsapp(telefone)}?text={quote(msg)}"

