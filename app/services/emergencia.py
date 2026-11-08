"""app/services/emergencia.py — Regras puras do Protocolo de Emergência (RN-001 v2.0).

Sem I/O: facilmente testável. Só decide *quando* a clínica está aberta, *quando* confiar no
timestamp enviado pelo cliente (auditoria jurídica) e monta o pacote de dados do disjuntor.
"""

import re
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import settings
from app.dependencies import agora_utc, garantir_utc
from app.models import Clinica
from app.services import links
from app.services.guardrails import GATILHOS_TEXTO_PUBLICO, PRIMEIROS_SOCORROS_NEGATIVOS

# A clínica só cadastra o fechamento; fora do 24h, considera-se que abre às 08:00.
HORARIO_ABERTURA_PADRAO = time(8, 0)

MODALIDADES = ("EMERGENCIA_A_CAMINHO", "RESGATE_SOLICITADO")


def _parse_hhmm(valor: str, padrao: time) -> time:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", valor or "")
    if not m:
        return padrao
    h, mi = int(m.group(1)), int(m.group(2))
    return time(h, mi) if h < 24 and mi < 60 else padrao


def clinica_aberta_agora(clinica: Clinica, agora: Optional[datetime] = None) -> bool:
    """24h → sempre aberta. Caso contrário: aberta entre 08:00 e `horario_fechamento` (fuso da clínica)."""
    if clinica.atendimento_24h:
        return True
    local = garantir_utc(agora or agora_utc()).astimezone(ZoneInfo(settings.timezone_clinica)).time()
    fechamento = _parse_hhmm(clinica.horario_fechamento, time(18, 0))
    return HORARIO_ABERTURA_PADRAO <= local < fechamento


def instante_alerta_confiavel(informado: Optional[datetime]) -> datetime:
    """
    Timestamp da exibição do alerta crítico (prova jurídica). Aceita o horário do dispositivo apenas
    se plausível (não futuro e de, no máximo, 6 h atrás); senão usa o relógio do servidor (UTC).
    """
    agora = agora_utc()
    if informado is None:
        return agora
    t = garantir_utc(informado)
    if t > agora + timedelta(minutes=2) or t < agora - timedelta(hours=6):
        return agora
    return min(t, agora)


def protocolo_publico(clinica: Clinica) -> dict:
    """Dados do disjuntor de emergência enviados ao frontend do tutor."""
    return {
        "atendimento_24h": clinica.atendimento_24h,
        "clinica_aberta_agora": clinica_aberta_agora(clinica),
        "horario_fechamento": clinica.horario_fechamento,
        "possui_veiculo_resgate": clinica.possui_veiculo_resgate,
        "whatsapp_plantao": clinica.telefone_emergencia,
        "endereco_completo": clinica.endereco_completo,
        "url_hospital_24h": links.URL_HOSPITAL_24H,
        "rota_clinica": links.rota_clinica_urls(clinica.endereco_completo, clinica.nome_fantasia),
        "primeiros_socorros_negativos": dict(PRIMEIROS_SOCORROS_NEGATIVOS),
        "gatilhos_texto": GATILHOS_TEXTO_PUBLICO,
    }
