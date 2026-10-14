"""
app/services/roi.py — Cálculo do ROI (RN-003).

Regra (defensável perante o cliente):
  economia por consulta = max(0, benchmark − duração real), SOMENTE para consultas
  finalizadas que tiveram Triagem Pré-Consulta preenchida. Nunca negativa.
  Capacidade extra = minutos economizados ÷ benchmark.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import garantir_utc
from app.models import Consulta, FormularioTriagem, RelatorioIA


def duracao_minutos(inicio: datetime, fim: datetime) -> float:
    """Duração em minutos (2 casas). Levanta ValueError se fim < início."""
    seg = (garantir_utc(fim) - garantir_utc(inicio)).total_seconds()
    if seg < 0:
        raise ValueError("fim_consulta anterior a inicio_consulta")
    return round(seg / 60, 2)


def minutos_economizados(duracao: float, benchmark: int, com_triagem: bool) -> float:
    if not com_triagem:
        return 0.0
    return round(max(0.0, benchmark - duracao), 2)


async def calcular_roi(
    db: AsyncSession,
    id_clinica: int,
    de: datetime,
    ate: datetime,
    id_medico: Optional[int] = None,
) -> dict:
    benchmark = settings.roi_benchmark_minutos
    tz = ZoneInfo(settings.timezone_clinica)
    de, ate = garantir_utc(de), garantir_utc(ate)

    filtros_base = [Consulta.id_clinica == id_clinica]
    if id_medico:
        filtros_base.append(Consulta.id_medico == id_medico)

    # --- Consultas finalizadas no período (RN-004: sempre escopadas por id_clinica) ---
    q_final = (
        select(
            Consulta.inicio_consulta,
            Consulta.fim_consulta,
            FormularioTriagem.id_formulario.is_not(None).label("com_triagem"),
        )
        .outerjoin(FormularioTriagem, FormularioTriagem.id_consulta == Consulta.id_consulta)
        .where(
            *filtros_base,
            Consulta.status == "finalizada",
            Consulta.inicio_consulta.is_not(None),
            Consulta.fim_consulta.is_not(None),
            Consulta.fim_consulta >= de,
            Consulta.fim_consulta <= ate,
        )
    )
    finalizadas = (await db.execute(q_final)).all()

    total_min = 0.0
    duracoes: list[float] = []
    com_triagem_n = 0
    por_dia: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for inicio, fim, com_triagem in finalizadas:
        try:
            dur = duracao_minutos(inicio, fim)
        except ValueError:
            continue  # registro inconsistente nunca contamina o ROI
        duracoes.append(dur)
        eco = minutos_economizados(dur, benchmark, bool(com_triagem))
        if com_triagem:
            com_triagem_n += 1
        total_min += eco
        dia = garantir_utc(fim).astimezone(tz).date().isoformat()
        por_dia[dia][0] += 1
        por_dia[dia][1] += eco

    # --- Adesão: consultas do período (não canceladas) vs triagens preenchidas ---
    data_ref = func.coalesce(Consulta.agendada_para, Consulta.criada_em)
    q_agenda = (
        select(
            func.count(Consulta.id_consulta),
            func.count(FormularioTriagem.id_formulario),
        )
        .outerjoin(FormularioTriagem, FormularioTriagem.id_consulta == Consulta.id_consulta)
        .where(*filtros_base, Consulta.status != "cancelada", data_ref >= de, data_ref <= ate)
    )
    total_agendadas, triagens = (await db.execute(q_agenda)).one()

    # --- Urgências identificadas ANTES da entrada em consultório (RN-001) ---
    q_urg = (
        select(func.count(FormularioTriagem.id_formulario))
        .join(Consulta, Consulta.id_consulta == FormularioTriagem.id_consulta)
        .outerjoin(RelatorioIA, RelatorioIA.id_formulario == FormularioTriagem.id_formulario)
        .where(
            *filtros_base,
            Consulta.status != "cancelada",
            data_ref >= de,
            data_ref <= ate,
            or_(
                FormularioTriagem.urgencia_deterministica.is_(True),
                RelatorioIA.flag_urgencia_detectada.is_(True),
            ),
            or_(
                Consulta.inicio_consulta.is_(None),
                FormularioTriagem.submetido_em <= Consulta.inicio_consulta,
            ),
        )
    )
    urgencias = (await db.execute(q_urg)).scalar_one()

    # Série contínua (dias sem consulta aparecem zerados no gráfico)
    serie = []
    d0, d1 = de.astimezone(tz).date(), ate.astimezone(tz).date()
    dia = d0
    while dia <= d1 and (d1 - d0).days <= 366:
        k = dia.isoformat()
        n, m = por_dia.get(k, [0, 0.0])
        serie.append({"dia": k, "consultas": int(n), "minutos_economizados": round(m, 2)})
        dia += timedelta(days=1)

    return {
        "de": de,
        "ate": ate,
        "benchmark_minutos": benchmark,
        "consultas_finalizadas": len(duracoes),
        "consultas_com_triagem": com_triagem_n,
        "minutos_economizados": round(total_min, 2),
        "horas_economizadas": round(total_min / 60, 2),
        "capacidade_extra_atendimentos": round(total_min / benchmark, 1) if benchmark else 0.0,
        "duracao_media_minutos": round(sum(duracoes) / len(duracoes), 1) if duracoes else None,
        "total_agendadas": int(total_agendadas),
        "triagens_realizadas": int(triagens),
        "taxa_adesao_pct": round(100 * triagens / total_agendadas, 1) if total_agendadas else 0.0,
        "urgencias_detectadas": int(urgencias),
        "urgencias_pct": round(100 * urgencias / triagens, 1) if triagens else 0.0,
        "serie_diaria": serie,
        "observacao": (
            f"Economia = max(0, {benchmark} min − duração real), apenas em consultas finalizadas com "
            "Triagem Pré-Consulta preenchida. Valores nunca negativos."
        ),
    }

