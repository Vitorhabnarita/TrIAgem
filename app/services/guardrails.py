"""
app/services/guardrails.py — Defesa em profundidade da REGRA ÉTICO-LEGAL.

Mesmo com System Prompt rígido, o texto gerado pela IA é verificado no servidor:
  - nenhum diagnóstico (definitivo ou presuntivo), prognóstico ou prescrição;
  - nenhum nome de doença;
  - sanitização do relato do tutor (dado NÃO confiável / Prompt Injection).
"""

import re
import unicodedata

from app.services.ai_schemas import (
    AVISO_GOVERNANCA_ETICA,
    COR_POR_NIVEL,
    BriefingIA,
    CorPrioridade,
    NivelPrioridade,
)

LIMITE_RELATO = 4000
LIMITE_CAMPO_CURTO = 500


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


# ---------------------------------------------------------------------------
# Padrões PROIBIDOS na saída da IA (aplicados em texto sem acento / minúsculo)
# ---------------------------------------------------------------------------

_PADROES_DIAGNOSTICO = [
    r"\bdiagnostic[oa]\s+(definitiv|presuntiv|provavel|final|de\s|e\s|:)",
    r"\bprognostic[oa]\s+(e|:|reservad|bom|ruim|favoravel|desfavoravel)",
    r"\b(compativel|compativeis)\s+com\b",
    r"\b(sugestiv[oa]s?|indicativ[oa]s?)\s+de\b",
    r"\bsugere\s+(um\s+|uma\s+)?(quadro|caso|processo|infeccao|doenca)\b",
    r"\bse\s+trata\s+de\b",
    r"\b(suspeita|suspeito|hipotese)\s+(de|diagnostica)\b",
    r"\bprovavelmente\s+(e|tem|sofre|trata|devido)\b",
    r"\b(o\s+)?(animal|pet|paciente|cao|gato|cachorro)\s+(tem|possui|sofre\s+de|esta\s+com\s+(a\s+)?doenca)\b",
    r"\bquadro\s+(de|clinico\s+de)\s+(gastroenterite|pancreatite|infeccao|intoxicacao|obstrucao)\b",
]

_DOENCAS = [
    "parvovirose", "cinomose", "leptospirose", "gastroenterite", "pancreatite",
    "insuficiencia renal", "doenca renal", "cistite", "urolitiase", "dirofilariose",
    "erliquiose", "babesiose", "leishmaniose", "torcao gastrica", "dilatacao gastrica",
    "piometra", "diabetes", "hipotireoidismo", "hipertireoidismo", "cardiomiopatia",
    "insuficiencia cardiaca", "epilepsia", "otite", "dermatite", "sarna", "giardiase",
    "verminose", "peritonite", "hepatite", "leucemia felina", "felv", "fiv", "panleucopenia",
    "rinotraqueite", "calicivirose", "tosse dos canis", "traqueobronquite", "neoplasia",
    "tumor", "cancer", "obstrucao uretral", "intoxicacao por", "envenenamento por",
    "pneumonia", "bronquite", "asma felina", "artrose", "displasia", "luxacao",
    "fratura", "colite", "gastrite", "ulcera", "anemia hemolitica", "icterícia",
]

_PADROES_PRESCRICAO = [
    r"\b\d+([.,]\d+)?\s*(mg|mcg|ml|ui|g)\s*(/|por\s+)\s*(kg|dia|hora|h)\b",
    r"\b(administr\w+|prescrev\w+|prescri\w+|receit\w+|medicar\s+com|aplicar|ministrar)\b[^.]{0,60}"
    r"\b(dipirona|paracetamol|ibuprofeno|prednisolona|prednisona|meloxicam|tramadol|"
    r"antibiotico|anti-?inflamatorio|amoxicilina|metronidazol|omeprazol|ondansetrona|"
    r"cefalexina|dexametasona|firocoxib|carprofeno|antiemetico|analgesico|vermifugo|corticoide)\b",
    r"\b(inicie|iniciar|instituir|instituir|recomendo|recomenda-se)\s+(o\s+)?(tratamento|terapia|conduta|antibioticoterapia)\b",
    r"\b(tratamento|terapia|conduta)\s+(com|de|recomendad[oa]|indicad[oa])\b",
]

_PADROES_DOENCA = [re.compile(r"\b" + re.escape(d) + r"\b") for d in _DOENCAS]
_PADROES_DIAG_RE = [re.compile(p) for p in _PADROES_DIAGNOSTICO]
_PADROES_PRESC_RE = [re.compile(p) for p in _PADROES_PRESCRICAO]


def _textos_do_briefing(b: BriefingIA) -> list[tuple[str, str]]:
    """Retorna (campo, texto) de TODOS os textos gerados. relato_leigo é exceção (palavras do tutor)."""
    textos: list[tuple[str, str]] = [
        ("resumo_estruturado", b.resumo_estruturado),
        ("cronologia_evolucao", b.cronologia_evolucao),
        ("orientacao_preparatoria_consultorio", b.orientacao_preparatoria_consultorio),
        ("alerta_seguranca_tutor", b.alerta_seguranca_tutor),
    ]
    textos += [("sinais_alerta_identificados", s) for s in b.sinais_alerta_identificados]
    textos += [("pontos_investigacao", s) for s in b.pontos_investigacao]
    textos += [("traducao.termo_tecnico", t.termo_tecnico_descritivo) for t in b.traducao_semiologica]
    # alerta_medicacao_e_bioindicadores: só checa prescrição/diagnóstico, não nomes de fármacos informados
    textos.append(("alerta_medicacao_e_bioindicadores", b.alerta_medicacao_e_bioindicadores))
    return textos


def verificar_violacoes_eticas(b: BriefingIA) -> list[str]:
    """Lista de violações encontradas (vazia = saída aprovada)."""
    violacoes: list[str] = []
    for campo, texto in _textos_do_briefing(b):
        t = _sem_acento(texto)
        for rx in _PADROES_DIAG_RE:
            if rx.search(t):
                violacoes.append(f"{campo}: padrão de diagnóstico ({rx.pattern[:40]}…)")
        for rx in _PADROES_PRESC_RE:
            if rx.search(t):
                violacoes.append(f"{campo}: padrão de prescrição ({rx.pattern[:40]}…)")
        if campo != "alerta_medicacao_e_bioindicadores":
            for rx in _PADROES_DOENCA:
                if rx.search(t):
                    violacoes.append(f"{campo}: nome de doença ('{rx.pattern[2:-2]}')")
    return violacoes


# ---------------------------------------------------------------------------
# Consistência RN-001: a IA nunca rebaixa a urgência determinística
# ---------------------------------------------------------------------------

PONTOS_PADRAO = [
    "Aferir parâmetros vitais na entrada: frequência cardíaca e respiratória, temperatura, TPC e coloração de mucosas.",
    "Avaliar estado de consciência, hidratação (turgor cutâneo) e escore de condição corporal.",
    "Realizar palpação abdominal e avaliar dor/desconforto em sistemas relacionados ao relato do tutor.",
    "Confirmar com o tutor início, evolução e eventuais medicações administradas em casa.",
]


def normalizar_briefing(b: BriefingIA, urgencia_deterministica: bool) -> BriefingIA:
    """Aplica regras determinísticas finais sobre a saída da IA (a IA sugere, o sistema garante)."""
    nivel = b.nivel_prioridade
    flag = b.flag_urgencia_detectada

    # Coerência interna da IA
    if flag and nivel != NivelPrioridade.EMERGENCIA:
        nivel = NivelPrioridade.EMERGENCIA
    if nivel == NivelPrioridade.EMERGENCIA:
        flag = True

    # RN-001 — gatilho determinístico prevalece sempre
    if urgencia_deterministica:
        flag = True
        nivel = NivelPrioridade.EMERGENCIA

    pontos = [p.strip() for p in b.pontos_investigacao if p and p.strip()][:4]
    for extra in PONTOS_PADRAO:
        if len(pontos) >= 3:
            break
        if extra not in pontos:
            pontos.append(extra)

    return b.model_copy(
        update={
            "flag_urgencia_detectada": flag,
            "nivel_prioridade": nivel,
            "cor_prioridade": COR_POR_NIVEL[nivel],
            "pontos_investigacao": pontos,
            "aviso_governanca_etica": AVISO_GOVERNANCA_ETICA,
        }
    )


# ---------------------------------------------------------------------------
# Sanitização do relato (Prompt Injection)
# ---------------------------------------------------------------------------

_PADROES_INJECAO = [
    r"ignor\w+\s+(todas?\s+)?(as\s+)?(instrucoes|regras|ordens|orientacoes)",
    r"(system|sistema)\s*(prompt|message|instruction)",
    r"voce\s+(agora\s+)?(e|sera|deve\s+ser)\s+um",
    r"(esqueca|desconsidere|ignore)\s+(tudo|o\s+que)",
    r"(responda|retorne|diga)\s+(apenas|somente)\b",
    r"\b(jailbreak|do\s+anything\s+now|dan\s+mode)\b",
    r"ignore\s+(all\s+|previous\s+|the\s+)*(instructions|rules)",
    r"</?\s*(relato|dados|system|instrucoes)[^>]*>",
]
_INJECAO_RE = [re.compile(p) for p in _PADROES_INJECAO]


def sanitizar_texto_tutor(texto: str, limite: int = LIMITE_RELATO) -> tuple[str, bool]:
    """
    Neutraliza o texto do tutor antes de entrar no prompt.
    Retorna (texto_limpo, suspeita_de_injecao).
    """
    texto = (texto or "").replace("\x00", "")
    texto = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]", "", texto)   # caracteres invisíveis/bidi
    suspeita = any(rx.search(_sem_acento(texto)) for rx in _INJECAO_RE)
    # Remove delimitadores que poderiam "fechar" a tag do prompt e escapar do contexto de dado
    texto = texto.replace("<", "‹").replace(">", "›")
    texto = re.sub(r"[ \t]{3,}", "  ", texto)
    texto = re.sub(r"\n{4,}", "\n\n\n", texto)
    return texto.strip()[:limite], suspeita


def briefing_seguro_deterministico(
    *,
    urgencia: bool,
    sintomas: list[str],
    sintomas_urgencia: list[str],
    medicamento_continuo: str,
    aspecto_urina_fezes: str,
    alteracao_peso_apetite: str,
    ingestao_hidrica: str,
    tempo_evolucao: str,
    relato: str,
) -> BriefingIA:
    """
    Relatório de contingência sem texto livre da IA — usado quando a saída da IA
    viola o guardrail ético. Apenas organiza dados estruturados já fornecidos.
    """
    nivel = NivelPrioridade.EMERGENCIA if urgencia else NivelPrioridade.NAO_URGENTE
    sinais = [f"Sintoma de urgência assinalado no checklist: {s}" for s in sintomas_urgencia]
    resumo = (
        "Relatório de contingência (organização automática de dados estruturados). "
        f"Sintomas assinalados: {', '.join(sintomas) if sintomas else 'nenhum'}. "
        f"Tempo de evolução informado: {tempo_evolucao}."
    )
    return BriefingIA(
        flag_urgencia_detectada=urgencia,
        nivel_prioridade=nivel,
        cor_prioridade=COR_POR_NIVEL[nivel],
        resumo_estruturado=resumo,
        traducao_semiologica=[],
        cronologia_evolucao=f"Evolução informada pelo tutor: {tempo_evolucao}.",
        alerta_medicacao_e_bioindicadores=(
            f"Medicação contínua/recente informada: {medicamento_continuo}. "
            f"Urina/fezes: {aspecto_urina_fezes}. Apetite/peso: {alteracao_peso_apetite}. "
            f"Ingestão hídrica: {ingestao_hidrica}."
        ),
        sinais_alerta_identificados=sinais,
        pontos_investigacao=list(PONTOS_PADRAO[:4]),
        orientacao_preparatoria_consultorio=(
            "Revisar o relato original do tutor e conduzir exame físico completo, "
            "sem conclusões prévias."
        ),
        alerta_seguranca_tutor=(
            "Procure atendimento de emergência presencial imediatamente. Não medique seu animal em casa."
            if urgencia
            else "Aguarde o atendimento. Não medique seu animal por conta própria; informe ao veterinário "
            "tudo o que já foi oferecido a ele."
        ),
        aviso_governanca_etica=AVISO_GOVERNANCA_ETICA,
    )

