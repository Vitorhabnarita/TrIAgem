"""app/services/links.py — Link único da Triagem Pré-Consulta, WhatsApp e links de emergência/GPS."""

import re
from typing import Optional
from urllib.parse import quote

from app.config import settings

URL_HOSPITAL_24H = "https://www.google.com/maps/search/Hospital+Veterinario+24h/"

_COORD_RE = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


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


# ---------------------------------------------------------------------------
# RN-001 v2.0 — Logística de emergência
# ---------------------------------------------------------------------------

def coordenadas(localizacao: Optional[str]) -> Optional[tuple[float, float]]:
    """(lat, lng) se a localização for um par de coordenadas válido; senão None (endereço livre)."""
    if not localizacao:
        return None
    m = _COORD_RE.match(localizacao)
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return lat, lng
    return None


def maps_url_localizacao(localizacao: Optional[str]) -> Optional[str]:
    """Link do Google Maps para a localização do tutor (coordenadas GPS ou endereço digitado)."""
    if not localizacao or not localizacao.strip():
        return None
    c = coordenadas(localizacao)
    if c:
        return f"https://www.google.com/maps/search/?api=1&query={c[0]},{c[1]}"
    return f"https://www.google.com/maps/search/?api=1&query={quote(localizacao.strip())}"


def rota_clinica_urls(endereco: Optional[str], clinica_nome: str) -> dict[str, str]:
    """Rotas (Google Maps e Waze) até a clínica; sem endereço cadastrado, busca pelo nome."""
    destino = (endereco or "").strip() or clinica_nome
    return {
        "google_maps": f"https://www.google.com/maps/dir/?api=1&destination={quote(destino)}&travelmode=driving",
        "waze": f"https://waze.com/ul?q={quote(destino)}&navigate=yes",
    }


def whatsapp_resgate_url(
    *, telefone_emergencia: Optional[str], clinica_nome: str, tutor_nome: str, pet_nome: str,
    maps_url: Optional[str],
) -> Optional[str]:
    """wa.me para o plantão da clínica com o link do Google Maps da localização exata do animal."""
    if not telefone_emergencia or not re.sub(r"\D", "", telefone_emergencia):
        return None
    msg = (
        f"🚨 EMERGÊNCIA — {clinica_nome}\n"
        f"Solicito VEÍCULO DE RESGATE para o pet {pet_nome} (tutor: {tutor_nome}).\n"
        f"📍 Localização do animal: {maps_url or 'não informada — por favor, ligue para mim'}"
    )
    return f"https://wa.me/{_telefone_whatsapp(telefone_emergencia)}?text={quote(msg)}"
