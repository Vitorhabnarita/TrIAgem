"""
scripts/seed.py — Catálogo de sintomas (com flag de urgência) e cenário demonstrativo veterinário.

Uso:
    python scripts/seed.py                 # só o catálogo de sintomas (idempotente)
    python scripts/seed.py --demo          # + Hospital Veterinário demo (idempotente)
    python scripts/seed.py --demo --reset-demo   # recria a agenda/histórico da clínica demo (datas de "hoje")

O cenário demo contém: 1 clínica, 2 médicos veterinários (CRMV), 3 usuários RBAC (recepção, médico,
gestor), pets de espécies/portes variados e consultas em todos os estados (triagem pendente, briefing
pronto, urgência RN-001, em andamento, finalizada com cronômetro UTC) + 14 dias de histórico para o BI.

As credenciais demo são geradas aleatoriamente e gravadas em `.demo_credentials.txt` (ignorado pelo git)
— nunca no código. O acesso 1-click do frontend usa POST /auth/demo/{papel} (DEMO_LOGIN_HABILITADO=true).
Os briefings do seed são textos DESCRITIVOS (sem diagnóstico/prescrição) e passam pelo mesmo guardrail
ético usado na IA real; a chamada ao Gemini NÃO é feita pelo seed.
"""

import argparse
import asyncio
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete, func, select  # noqa: E402

from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Clinica,
    Consulta,
    FormularioTriagem,
    MedicoVeterinario,
    Pet,
    RelatorioIA,
    Sintoma,
    Tutor,
    Usuario,
)
from app.security import gerar_token_triagem, hash_senha  # noqa: E402
from app.services.ai_schemas import (  # noqa: E402
    BriefingIA,
    CorPrioridade,
    NivelPrioridade,
    TraducaoSemiologica,
)
from app.services.guardrails import normalizar_briefing, verificar_violacoes_eticas  # noqa: E402

CNPJ_DEMO = "00.000.000/0001-91"
NOME_CLINICA_DEMO = "Hospital Veterinário Vida Pet 24h"
MODELO_SEED = "seed-demonstrativo"

# (nome, urgência, categoria)
CATALOGO: list[tuple[str, bool, str]] = [
    # --- Sinais de URGÊNCIA (RN-001 — gatilho determinístico) ---
    ("Convulsão (tremores, rigidez ou perda de controle do corpo)", True, "Emergência"),
    ("Dificuldade grave para respirar / falta de ar", True, "Emergência"),
    ("Sangramento ativo ou que não para", True, "Emergência"),
    ("Desmaio ou perda de consciência", True, "Emergência"),
    ("Tentativa de urinar sem sucesso (faz esforço e não sai nada)", True, "Emergência"),
    ("Tentativa de vomitar sem sucesso com barriga inchada", True, "Emergência"),
    ("Suspeita de ingestão de veneno, remédio ou produto tóxico", True, "Emergência"),
    ("Atropelamento, queda de altura ou trauma grave", True, "Emergência"),
    ("Gengivas muito pálidas, azuladas ou roxas", True, "Emergência"),
    ("Barriga muito inchada e dura", True, "Emergência"),
    ("Dor intensa (grita ou não deixa ser tocado)", True, "Emergência"),
    # --- Digestivo ---
    ("Vômito", False, "Digestivo"),
    ("Diarreia", False, "Digestivo"),
    ("Fezes com sangue ou muco", False, "Digestivo"),
    ("Falta de apetite", False, "Digestivo"),
    ("Salivação excessiva", False, "Digestivo"),
    ("Mau hálito ou dificuldade para mastigar", False, "Digestivo"),
    # --- Respiratório ---
    ("Tosse", False, "Respiratório"),
    ("Espirros frequentes", False, "Respiratório"),
    ("Secreção no nariz", False, "Respiratório"),
    ("Respiração mais rápida que o normal", False, "Respiratório"),
    # --- Urinário ---
    ("Urina com mais frequência", False, "Urinário"),
    ("Urina com sangue ou cheiro muito forte", False, "Urinário"),
    ("Bebendo muito mais água que o normal", False, "Urinário"),
    # --- Pele e ouvidos ---
    ("Coceira intensa", False, "Pele e ouvidos"),
    ("Queda de pelo ou falhas no pelo", False, "Pele e ouvidos"),
    ("Feridas ou caroços na pele", False, "Pele e ouvidos"),
    ("Sacode a cabeça / mau cheiro no ouvido", False, "Pele e ouvidos"),
    ("Secreção ou vermelhidão nos olhos", False, "Pele e ouvidos"),
    # --- Locomotor / comportamento ---
    ("Manca ou tem dificuldade para andar", False, "Locomotor"),
    ("Dor ao levantar ou subir escadas", False, "Locomotor"),
    ("Apatia, prostração ou muito sonolento", False, "Comportamento"),
    ("Mudança de comportamento (agressivo, escondido, ansioso)", False, "Comportamento"),
    ("Perda de peso", False, "Comportamento"),
    ("Sensação de febre (corpo quente, tremores leves)", False, "Comportamento"),
]

# Atalhos (nomes exatos do catálogo)
S_EMESE_IMPRODUTIVA = "Tentativa de vomitar sem sucesso com barriga inchada"
S_BARRIGA_DURA = "Barriga muito inchada e dura"
S_URINAR_SEM_SUCESSO = "Tentativa de urinar sem sucesso (faz esforço e não sai nada)"
S_FALTA_AR = "Dificuldade grave para respirar / falta de ar"


async def seed_sintomas() -> None:
    async with AsyncSessionLocal() as db:
        existentes = {s.nome_sintoma: s for s in (await db.execute(select(Sintoma))).scalars()}
        novos = 0
        for nome, urgencia, categoria in CATALOGO:
            s = existentes.get(nome)
            if s is None:
                db.add(Sintoma(nome_sintoma=nome, alerta_urgencia=urgencia, categoria=categoria, ativo=True))
                novos += 1
            else:
                s.alerta_urgencia, s.categoria = urgencia, categoria
        await db.commit()
        print(f"[seed] sintomas: {novos} novos, {len(CATALOGO) - novos} atualizados.")


# ---------------------------------------------------------------------------
# Cenário demonstrativo veterinário
# ---------------------------------------------------------------------------

def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _briefing(*, urgencia: bool, nivel: NivelPrioridade, resumo: str,
              traducao: list[tuple[str, str]], cronologia: str, med_bio: str,
              sinais: list[str], pontos: list[str], orientacao: str, seguranca: str) -> BriefingIA:
    """Monta o briefing, aplica as regras determinísticas e valida contra o guardrail ético."""
    b = BriefingIA(
        flag_urgencia_detectada=urgencia,
        nivel_prioridade=nivel,
        cor_prioridade=CorPrioridade.AZUL,  # recalculada por normalizar_briefing
        resumo_estruturado=resumo,
        traducao_semiologica=[
            TraducaoSemiologica(relato_leigo=a, termo_tecnico_descritivo=t) for a, t in traducao
        ],
        cronologia_evolucao=cronologia,
        alerta_medicacao_e_bioindicadores=med_bio,
        sinais_alerta_identificados=sinais,
        pontos_investigacao=pontos,
        orientacao_preparatoria_consultorio=orientacao,
        alerta_seguranca_tutor=seguranca,
    )
    b = normalizar_briefing(b, urgencia)
    violacoes = verificar_violacoes_eticas(b)
    if violacoes:  # o seed nunca grava texto que a IA real seria proibida de gerar
        raise RuntimeError(f"Briefing do seed viola o guardrail ético: {violacoes}")
    return b


_ORIENTACAO_URGENTE = (
    "Paciente com Alerta de Emergência (RN-001): priorizar a entrada. Realizar exame físico completo e "
    "presencial, sem restringir a avaliação aos sinais relatados. Este briefing apenas organiza o relato do "
    "tutor e não substitui a avaliação clínica do médico veterinário."
)
_ORIENTACAO_ROTINA = (
    "Realizar exame físico completo e presencial, avaliando todos os sistemas independentemente dos sinais "
    "relatados. Este briefing apenas organiza o relato do tutor e não induz conclusões clínicas."
)


def _casos_do_dia() -> list[dict]:
    """Casos clínicos demonstrativos de HOJE (status variados)."""
    return [
        # 1) Pastor Alemão — emergência (RN-001 determinístico) — AGUARDANDO atendimento
        dict(
            medico=0, status="agendada", min_agenda=+5,
            tutor=("Carlos Eduardo Lima", "11987654321"),
            pet=dict(nome="Thor", especie="Cão", raca="Pastor Alemão", sexo="Macho", idade_texto="4 anos",
                     peso_kg=Decimal("38.00"), porte="Grande", status_reprodutivo="Inteiro"),
            triagem=dict(
                ambiente="Casa com quintal · Com acesso à rua",
                alimentacao="Ração seca (1 refeição noturna volumosa)",
                vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=False,
                manejo_preventivo="Vacinas: V10 e antirrábica em dia. Vermífugo há 2 meses. Antipulgas/carrapatos: em dia. "
                                  "Acesso à rua: sim. Contactantes: nenhum.",
                medicamento_continuo="Nenhum medicamento contínuo; nada administrado nas últimas 48 h",
                aspecto_urina_fezes="Urinou normal pela manhã; não defecou desde o início do mal-estar",
                alteracao_peso_apetite="Apetite normal até o jantar; sem alteração de peso",
                ingestao_hidrica="Bebeu normalmente durante o dia",
                tempo_evolucao="Cerca de 2 horas",
                relato_livre_tutor="O Thor começou a ficar muito agitado depois do jantar, fica tentando vomitar mas não "
                                   "sai nada, só uma baba espumosa. A barriga está inchada e dura, ele anda de um lado "
                                   "para o outro e não consegue deitar. Começou há umas 2 horas.",
                sintomas=[S_EMESE_IMPRODUTIVA, S_BARRIGA_DURA, "Salivação excessiva",
                          "Apatia, prostração ou muito sonolento"],
                minutos_atras=18,
            ),
            briefing=dict(
                urgencia=True, nivel=NivelPrioridade.EMERGENCIA,
                resumo="Paciente canino, Pastor Alemão, macho inteiro, 38 kg, com êmese improdutiva (ânsia), sialorreia e "
                       "distensão abdominal de início agudo há cerca de 2 horas, associadas a inquietação e incapacidade de "
                       "manter decúbito. Tutor refere refeição volumosa pouco antes do início do quadro. Checklist de "
                       "urgência assinalado (RN-001).",
                traducao=[
                    ("tentando vomitar mas não sai nada", "Êmese improdutiva (ânsia de vômito)"),
                    ("baba espumosa", "Sialorreia"),
                    ("barriga inchada e dura", "Distensão abdominal com aumento de tensão referido pelo tutor"),
                    ("anda de um lado para o outro e não consegue deitar", "Inquietação com incapacidade de manter decúbito"),
                ],
                cronologia="Há ~2 horas, após a refeição noturna: ânsia de vômito improdutiva → sialorreia → aumento "
                           "progressivo do volume abdominal → inquietação sem conseguir deitar.",
                med_bio="Medicação contínua: nenhuma informada (nada administrado nas últimas 48 h). Bioindicadores: sem "
                        "defecação desde o início do quadro; urina normal pela manhã; ingestão hídrica normal; apetite "
                        "preservado até o jantar.",
                sinais=["Êmese improdutiva com abdômen distendido (RN-001)", "Barriga muito inchada e dura (checklist de urgência)",
                        "Inquietação com incapacidade de deitar", "Sialorreia"],
                pontos=["Aferir imediatamente TPC, coloração de mucosas, frequências cardíaca e respiratória e qualidade do pulso.",
                        "Avaliar grau de distensão abdominal, percussão e dor à palpação abdominal.",
                        "Aferir temperatura retal e estado de hidratação.",
                        "Confirmar com o tutor horário da última refeição, volume ingerido e acesso a objetos ou substâncias."],
                orientacao=_ORIENTACAO_URGENTE,
                seguranca="Os sinais informados exigem avaliação veterinária imediata. Leve o Thor agora à clínica ou ao "
                          "pronto-socorro veterinário, sem aguardar. Não ofereça comida, água, remédios ou qualquer produto "
                          "por conta própria.",
            ),
        ),
        # 2) Gato Persa — emergência (RN-001 determinístico) — AGUARDANDO atendimento
        dict(
            medico=0, status="agendada", min_agenda=+12,
            tutor=("Fernanda Souza Martins", "21998761234"),
            pet=dict(nome="Simba", especie="Gato", raca="Persa", sexo="Macho", idade_texto="6 anos",
                     peso_kg=Decimal("5.00"), porte="Pequeno", status_reprodutivo="Castrado"),
            triagem=dict(
                ambiente="Apartamento · Sem acesso à rua",
                alimentacao="Ração seca e sachê úmido",
                vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=False,
                manejo_preventivo="Vacinas: V4/V5 e antirrábica em dia. Vermífugo há 4 meses. Antipulgas: em dia. "
                                  "Acesso à rua: não. Contactantes: nenhum.",
                medicamento_continuo="Nenhum medicamento contínuo; nada administrado nas últimas 48 h",
                aspecto_urina_fezes="Sem urina na caixa de areia desde ontem à noite; fezes normais",
                alteracao_peso_apetite="Come menos desde ontem; peso aparentemente estável",
                ingestao_hidrica="Está bebendo menos água que o habitual",
                tempo_evolucao="Desde ontem à noite (cerca de 12 horas)",
                relato_livre_tutor="O Simba entra e sai da caixa de areia a toda hora, faz força, mia de dor e não sai xixi "
                                   "nenhum. Ele está escondido e lambendo muito a região da barriga e de baixo do rabo. "
                                   "Vomitou uma vez hoje cedo. Começou ontem à noite.",
                sintomas=[S_URINAR_SEM_SUCESSO, "Vômito", "Apatia, prostração ou muito sonolento",
                          "Mudança de comportamento (agressivo, escondido, ansioso)"],
                minutos_atras=25,
            ),
            briefing=dict(
                urgencia=True, nivel=NivelPrioridade.EMERGENCIA,
                resumo="Paciente felino, Persa, macho castrado, 5 kg, com esforço miccional improdutivo (estrangúria/disúria "
                       "com possível anúria, a confirmar no exame físico) há cerca de 12 horas, associado a vocalização, "
                       "lambedura da região urogenital, isolamento, hiporexia e 1 episódio de êmese. Checklist de urgência "
                       "assinalado (RN-001).",
                traducao=[
                    ("faz força na caixa de areia e não sai xixi nenhum",
                     "Estrangúria/disúria com possível anúria (a confirmar no exame físico)"),
                    ("mia de dor", "Vocalização associada a desconforto doloroso referido"),
                    ("lambendo muito a região de baixo do rabo", "Lambedura excessiva da região urogenital"),
                    ("está escondido", "Isolamento / alteração comportamental"),
                    ("vomitou uma vez", "Êmese (1 episódio)"),
                ],
                cronologia="Ontem à noite: idas frequentes à caixa de areia com esforço miccional → madrugada: vocalização, "
                           "lambedura urogenital e isolamento → hoje cedo: 1 episódio de êmese.",
                med_bio="Medicação contínua: nenhuma informada (nada administrado nas últimas 48 h). Bioindicadores: sem "
                        "urina em caixa de areia há ~12 h; fezes normais; ingestão hídrica diminuída; hiporexia desde ontem.",
                sinais=["Tentativa improdutiva de urinar (RN-001)", "Prostração e isolamento",
                        "Êmese associada", "Vocalização com desconforto doloroso referido"],
                pontos=["Aferir mucosas, TPC, frequência cardíaca (atentar a bradicardia ou arritmia), frequência respiratória "
                        "e temperatura retal.",
                        "Palpar a região abdominal caudal avaliando tamanho, tensão e dor da vesícula urinária; inspecionar "
                        "a região prepucial/peniana.",
                        "Avaliar estado de consciência e grau de hidratação.",
                        "Confirmar com o tutor o último momento em que urinou e se há histórico de episódios semelhantes."],
                orientacao=_ORIENTACAO_URGENTE,
                seguranca="Os sinais informados exigem avaliação veterinária imediata. Leve o Simba agora à clínica ou ao "
                          "pronto-socorro veterinário. Não dê remédios, líquidos forçados ou qualquer produto por conta própria.",
            ),
        ),
        # 3) Poodle idoso — AMARELO (sem urgência determinística)
        dict(
            medico=0, status="agendada", min_agenda=+30,
            tutor=("Helena Ribeiro Prado", "11976543210"),
            pet=dict(nome="Luna", especie="Cão", raca="Poodle", sexo="Fêmea", idade_texto="11 anos",
                     peso_kg=Decimal("7.20"), porte="Pequeno", status_reprodutivo="Castrado"),
            triagem=dict(
                ambiente="Apartamento · Passeios diários na rua",
                alimentacao="Ração seca sênior e petiscos",
                vacinacao_em_dia=True, vermifugo_em_dia=False, convivio_outros_animais=True,
                manejo_preventivo="Vacinas: V10 e antirrábica em dia. Vermífugo atrasado (último há 8 meses). Antipulgas "
                                  "aplicado há 20 dias. Acesso à rua: passeios. Contactantes: 1 cão idoso na casa.",
                medicamento_continuo="Suplemento articular (condroitina) diário; antipulgas aplicado há 20 dias",
                aspecto_urina_fezes="Urina clara e em grande volume; fezes normais",
                alteracao_peso_apetite="Apetite preservado; peso parece estável",
                ingestao_hidrica="Aumentada: esvazia o pote várias vezes ao dia",
                tempo_evolucao="Mais de 1 mês",
                relato_livre_tutor="A Luna está bebendo água o tempo todo há mais de um mês e faz xixi em casa, coisa que nunca "
                                   "fazia. O pelo da barriga e das costas está caindo em falhas e a pele ficou escura. Ela come "
                                   "bem, mas está um pouco mais cansada nas caminhadas.",
                sintomas=["Bebendo muito mais água que o normal", "Urina com mais frequência",
                          "Queda de pelo ou falhas no pelo"],
                minutos_atras=40,
            ),
            briefing=dict(
                urgencia=False, nivel=NivelPrioridade.URGENTE,
                resumo="Paciente canino, Poodle, fêmea castrada, 11 anos, 7,2 kg, com polidipsia e poliúria de evolução "
                       "superior a 1 mês, mudança do hábito miccional (micção fora do local habitual), alopecia multifocal "
                       "com hiperpigmentação cutânea e menor tolerância ao exercício referida. Apetite preservado. Sem sinais "
                       "de risco imediato informados.",
                traducao=[
                    ("bebendo água o tempo todo", "Polidipsia"),
                    ("faz xixi em casa, coisa que nunca fazia", "Poliúria com alteração do hábito miccional"),
                    ("pelo caindo em falhas", "Alopecia multifocal"),
                    ("a pele ficou escura", "Hiperpigmentação cutânea"),
                    ("mais cansada nas caminhadas", "Intolerância ao exercício referida"),
                ],
                cronologia="Há mais de 1 mês: aumento da ingestão de água → aumento do volume e da frequência urinária com "
                           "micção fora do local habitual → alopecia em falhas em abdome e dorso com escurecimento da pele → "
                           "recentemente: menor tolerância às caminhadas.",
                med_bio="Medicação em uso: suplemento articular diário e antiparasitário externo aplicado há 20 dias — "
                        "conferir produtos e posologia com o tutor. Bioindicadores: ingestão hídrica aumentada; urina clara em "
                        "grande volume; apetite e peso estáveis; vermifugação atrasada.",
                sinais=["Polidipsia e poliúria de evolução crônica", "Alopecia multifocal com hiperpigmentação",
                        "Intolerância ao exercício (referida)"],
                pontos=["Aferir peso atual e escore de condição corporal; comparar com registros anteriores, se houver.",
                        "Avaliar mucosas, TPC, hidratação, frequências cardíaca e respiratória e temperatura retal.",
                        "Realizar auscultação cardiopulmonar e palpação abdominal (volume abdominal e vesical).",
                        "Examinar pele e pelagem: distribuição da alopecia, prurido, lesões e presença de ectoparasitas."],
                orientacao=_ORIENTACAO_ROTINA,
                seguranca="Os sinais descritos merecem avaliação veterinária em breve e não indicam risco imediato pelas "
                          "informações enviadas. Aguarde ser chamado e não ofereça remédios ou suplementos novos por conta "
                          "própria. Se ela piorar de repente, avise a recepção imediatamente.",
            ),
        ),
        # 4) Em andamento (cronômetro ativo)
        dict(
            medico=0, status="em_andamento", min_agenda=-20, inicio_min_atras=9,
            tutor=("Patrícia Gomes Nunes", "11965432109"),
            pet=dict(nome="Nina", especie="Cão", raca="Shih Tzu", sexo="Fêmea", idade_texto="5 anos",
                     peso_kg=Decimal("6.10"), porte="Pequeno", status_reprodutivo="Castrado"),
            triagem=dict(
                ambiente="Apartamento · Passeios curtos na rua",
                alimentacao="Ração seca",
                vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=False,
                manejo_preventivo="Vacinas: V10 e antirrábica em dia. Vermífugo há 3 meses. Antipulgas: em dia. Contactantes: nenhum.",
                medicamento_continuo="Nenhum medicamento contínuo; nada administrado nas últimas 48 h",
                aspecto_urina_fezes="Urina e fezes normais",
                alteracao_peso_apetite="Sem alterações de apetite ou peso",
                ingestao_hidrica="Normal",
                tempo_evolucao="3 dias",
                relato_livre_tutor="A Nina está espirrando bastante há 3 dias e escorre uma secreção clara do nariz. "
                                   "Continua brincando e comendo normalmente.",
                sintomas=["Espirros frequentes", "Secreção no nariz"],
                minutos_atras=35,
            ),
            briefing=dict(
                urgencia=False, nivel=NivelPrioridade.POUCO_URGENTE,
                resumo="Paciente canino, Shih Tzu, fêmea castrada, 5 anos, 6,1 kg, com espirros frequentes e secreção nasal "
                       "serosa há 3 dias. Mantém apetite, atividade e padrões normais de urina e fezes. Sem sinais de risco "
                       "imediato informados.",
                traducao=[("espirrando bastante", "Espirros frequentes"),
                          ("escorre uma secreção clara do nariz", "Descarga nasal serosa")],
                cronologia="Há 3 dias: início de espirros frequentes e descarga nasal serosa, sem alteração de apetite ou "
                           "comportamento.",
                med_bio="Medicação contínua: nenhuma informada. Bioindicadores: urina e fezes normais; apetite, ingestão "
                        "hídrica e peso sem alterações.",
                sinais=[],
                pontos=["Aferir temperatura retal, frequências cardíaca e respiratória e coloração de mucosas.",
                        "Avaliar a descarga nasal (aspecto, uni ou bilateral) e padrão respiratório.",
                        "Realizar auscultação cardiopulmonar e palpação de linfonodos submandibulares.",
                        "Confirmar com o tutor contato com outros animais e ambiente recente."],
                orientacao=_ORIENTACAO_ROTINA,
                seguranca="Pelas informações enviadas não há sinais de risco imediato. Aguarde ser chamado e não ofereça "
                          "remédios por conta própria. Se notar dificuldade para respirar, avise a recepção na hora.",
            ),
        ),
        # 5) Triagem PENDENTE — aguardando o tutor (médico 0)
        dict(medico=0, status="agendada", min_agenda=+45,
             tutor=("Rodrigo Alves Teixeira", "11954321098"),
             pet=dict(nome="Frida", especie="Gato", raca="Sem raça definida (SRD)", sexo="Fêmea", idade_texto="2 anos",
                      peso_kg=Decimal("3.60"), porte="Pequeno", status_reprodutivo="Castrado")),
        # 6) Triagem PENDENTE — filhote para consulta de rotina (médico 1)
        dict(medico=1, status="agendada", min_agenda=+60,
             tutor=("Juliana Costa Barbosa", "11943210987"),
             pet=dict(nome="Pipoca", especie="Cão", raca="Sem raça definida (SRD)", sexo="Fêmea", idade_texto="3 meses",
                      peso_kg=Decimal("2.40"), porte="Mini", status_reprodutivo="Inteiro")),
        # 7) Finalizada hoje — Beagle (cronômetro UTC: 14 min)
        dict(
            medico=0, status="finalizada", min_agenda=-130, inicio_min_atras=115, duracao_min=14,
            tutor=("Marcos Vinícius Rocha", "11932109876"),
            pet=dict(nome="Bidu", especie="Cão", raca="Beagle", sexo="Macho", idade_texto="6 anos",
                     peso_kg=Decimal("14.30"), porte="Médio", status_reprodutivo="Castrado"),
            triagem=dict(
                ambiente="Casa com quintal · Com acesso à rua",
                alimentacao="Ração seca e petiscos",
                vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=True,
                manejo_preventivo="Vacinas: V10 e antirrábica em dia. Vermífugo há 2 meses. Antipulgas/carrapatos: em dia. "
                                  "Acesso à rua: sim. Contactantes: 2 cães.",
                medicamento_continuo="Nenhum medicamento contínuo; nada administrado nas últimas 48 h",
                aspecto_urina_fezes="Normais",
                alteracao_peso_apetite="Sem alterações",
                ingestao_hidrica="Normal",
                tempo_evolucao="1 semana",
                relato_livre_tutor="O Bidu balança a cabeça o tempo todo, se coça atrás da orelha direita e o ouvido está "
                                   "com um cheiro forte há uma semana.",
                sintomas=["Sacode a cabeça / mau cheiro no ouvido", "Coceira intensa"],
                minutos_atras=140,
            ),
            briefing=dict(
                urgencia=False, nivel=NivelPrioridade.POUCO_URGENTE,
                resumo="Paciente canino, Beagle, macho castrado, 6 anos, 14,3 kg, com head shaking, prurido auricular à "
                       "direita e odor ótico referido há 1 semana. Demais sistemas sem alterações relatadas.",
                traducao=[("balança a cabeça o tempo todo", "Sacudidas cefálicas frequentes (head shaking)"),
                          ("se coça atrás da orelha direita", "Prurido auricular à direita"),
                          ("ouvido com cheiro forte", "Odor ótico referido")],
                cronologia="Há 1 semana: início de sacudidas de cabeça e prurido auricular à direita, com odor ótico associado.",
                med_bio="Medicação contínua: nenhuma informada. Bioindicadores: urina, fezes, apetite e ingestão hídrica normais.",
                sinais=[],
                pontos=["Aferir temperatura retal e parâmetros vitais de entrada.",
                        "Realizar otoscopia bilateral e avaliar aspecto de conduto e secreção.",
                        "Examinar pele e pelagem em busca de ectoparasitas e lesões de coçadura.",
                        "Confirmar com o tutor frequência de banhos e eventual entrada de água nos ouvidos."],
                orientacao=_ORIENTACAO_ROTINA,
                seguranca="Pelas informações enviadas não há sinais de risco imediato. Não coloque produtos no ouvido do "
                          "Bidu por conta própria e aguarde ser chamado.",
            ),
        ),
        # 8) Finalizada hoje — Golden (11 min)
        dict(
            medico=1, status="finalizada", min_agenda=-100, inicio_min_atras=85, duracao_min=11,
            tutor=("Beatriz Lemos Ferraz", "11921098765"),
            pet=dict(nome="Mel", especie="Cão", raca="Golden Retriever", sexo="Fêmea", idade_texto="8 anos",
                     peso_kg=Decimal("30.50"), porte="Grande", status_reprodutivo="Castrado"),
            triagem=dict(
                ambiente="Casa com quintal · Passeios diários",
                alimentacao="Ração seca",
                vacinacao_em_dia=True, vermifugo_em_dia=True, convivio_outros_animais=False,
                manejo_preventivo="Vacinas: V10 e antirrábica em dia. Vermífugo há 3 meses. Antipulgas/carrapatos: em dia. Contactantes: nenhum.",
                medicamento_continuo="Nenhum medicamento contínuo; nada administrado nas últimas 48 h",
                aspecto_urina_fezes="Normais",
                alteracao_peso_apetite="Apetite normal; ganhou peso no último ano",
                ingestao_hidrica="Normal",
                tempo_evolucao="2 semanas",
                relato_livre_tutor="A Mel está mancando da pata de trás esquerda e demora para levantar de manhã. "
                                   "Parou de subir no sofá.",
                sintomas=["Manca ou tem dificuldade para andar", "Dor ao levantar ou subir escadas"],
                minutos_atras=110,
            ),
            briefing=dict(
                urgencia=False, nivel=NivelPrioridade.POUCO_URGENTE,
                resumo="Paciente canino, Golden Retriever, fêmea castrada, 8 anos, 30,5 kg, com claudicação de membro "
                       "pélvico esquerdo, rigidez ao levantar e relutância em subir em superfícies elevadas há 2 semanas.",
                traducao=[("mancando da pata de trás esquerda", "Claudicação de membro pélvico esquerdo"),
                          ("demora para levantar de manhã", "Rigidez ao levantar"),
                          ("parou de subir no sofá", "Relutância em saltar/subir em superfícies")],
                cronologia="Há 2 semanas: início de claudicação pélvica esquerda → progressão com rigidez matinal e "
                           "relutância em subir no sofá.",
                med_bio="Medicação contínua: nenhuma informada (nenhum analgésico ou anti-inflamatório administrado em casa "
                        "nas últimas 48 h). Bioindicadores normais; ganho de peso no último ano.",
                sinais=[],
                pontos=["Aferir peso e escore de condição corporal.",
                        "Observar a marcha à distância e a distribuição de apoio entre os membros.",
                        "Realizar palpação e mobilização articular dos membros pélvicos, avaliando dor e amplitude.",
                        "Confirmar com o tutor episódios de trauma, tipo de piso e atividade física recente."],
                orientacao=_ORIENTACAO_ROTINA,
                seguranca="Pelas informações enviadas não há sinais de risco imediato. Evite exercícios intensos até a "
                          "consulta e não ofereça remédios para dor por conta própria.",
            ),
        ),
    ]


# Pacientes recorrentes do histórico (alimentam o BI dos últimos 14 dias)
_HISTORICO_PACIENTES = [
    dict(tutor=("Antônio Pereira Neto", "11910987654"),
         pet=dict(nome="Rex", especie="Cão", raca="Labrador", sexo="Macho", idade_texto="7 anos",
                  peso_kg=Decimal("32.00"), porte="Grande", status_reprodutivo="Castrado"),
         sintomas=["Diarreia", "Falta de apetite"],
         traducao=[("fezes moles desde ontem", "Fezes pastosas/diarreia"), ("não quis comer", "Hiporexia")],
         resumo="Paciente canino, 7 anos, com fezes pastosas e hiporexia de início recente."),
    dict(tutor=("Larissa Duarte Campos", "11909876543"),
         pet=dict(nome="Mia", especie="Gato", raca="Sem raça definida (SRD)", sexo="Fêmea", idade_texto="3 anos",
                  peso_kg=Decimal("4.00"), porte="Pequeno", status_reprodutivo="Castrado"),
         sintomas=["Vômito", "Apatia, prostração ou muito sonolento"],
         traducao=[("vomitando desde cedo", "Êmese"), ("quietinha", "Hipoatividade/apatia")],
         resumo="Paciente felino, 3 anos, com êmese e hipoatividade referidas."),
    dict(tutor=("Gabriel Moreira Silva", "11998765432"),
         pet=dict(nome="Toby", especie="Cão", raca="Shih Tzu", sexo="Macho", idade_texto="9 anos",
                  peso_kg=Decimal("7.00"), porte="Pequeno", status_reprodutivo="Castrado"),
         sintomas=["Tosse", "Respiração mais rápida que o normal"],
         traducao=[("tosse seca à noite", "Tosse seca noturna"), ("respira rápido", "Taquipneia")],
         resumo="Paciente canino, 9 anos, com tosse seca noturna e taquipneia referidas."),
    dict(tutor=("Camila Andrade Lopes", "11987650001"),
         pet=dict(nome="Princesa", especie="Cão", raca="Yorkshire", sexo="Fêmea", idade_texto="2 anos",
                  peso_kg=Decimal("3.10"), porte="Mini", status_reprodutivo="Inteiro"),
         sintomas=["Coceira intensa"],
         traducao=[("se coça muito", "Prurido intenso")],
         resumo="Paciente canino, 2 anos, com prurido intenso referido."),
    dict(tutor=("Eduardo Farias Santos", "11987650002"),
         pet=dict(nome="Bob", especie="Cão", raca="Bulldog Francês", sexo="Macho", idade_texto="4 anos",
                  peso_kg=Decimal("12.40"), porte="Pequeno", status_reprodutivo="Inteiro"),
         sintomas=[S_FALTA_AR],
         traducao=[("respiração com barulho e muito esforço", "Dispneia com esforço respiratório audível")],
         resumo="Paciente canino braquicefálico, 4 anos, com esforço respiratório audível referido.",
         urgencia=True),
    dict(tutor=("Vanessa Cardoso Melo", "11987650003"),
         pet=dict(nome="Amora", especie="Gato", raca="Siamês", sexo="Fêmea", idade_texto="1 ano",
                  peso_kg=Decimal("3.00"), porte="Pequeno", status_reprodutivo="Castrado"),
         sintomas=["Secreção ou vermelhidão nos olhos"],
         traducao=[("olho lacrimejando e vermelho", "Epífora e hiperemia conjuntival")],
         resumo="Paciente felino, 1 ano, com epífora e hiperemia ocular referidas."),
]
_DURACOES = [12, 15, 14, 18, 11, 16, 13, 17, 19, 12, 14, 15, 16, 13, 18, 12, 15, 14]
_SEM_TRIAGEM = {4, 9, 15}  # consultas do histórico sem triagem (reduz a taxa de adesão de forma realista)


def _briefing_historico(p: dict) -> BriefingIA:
    urg = bool(p.get("urgencia"))
    return _briefing(
        urgencia=urg,
        nivel=NivelPrioridade.EMERGENCIA if urg else NivelPrioridade.POUCO_URGENTE,
        resumo=p["resumo"], traducao=p["traducao"],
        cronologia="Início recente conforme relato do tutor, sem detalhamento adicional.",
        med_bio="Medicação contínua: nenhuma informada. Bioindicadores sem alterações relevantes relatadas.",
        sinais=["Sinal de urgência assinalado no checklist (RN-001)"] if urg else [],
        pontos=["Aferir parâmetros vitais de entrada: TPC, mucosas, frequências cardíaca e respiratória e temperatura retal.",
                "Realizar exame físico completo por sistemas, incluindo auscultação cardiopulmonar e palpação abdominal.",
                "Avaliar estado de hidratação e escore de condição corporal.",
                "Confirmar com o tutor início, evolução e medicações administradas em casa."],
        orientacao=_ORIENTACAO_URGENTE if urg else _ORIENTACAO_ROTINA,
        seguranca=("Os sinais informados exigem avaliação veterinária imediata. Procure atendimento agora e não ofereça "
                   "remédios por conta própria." if urg else
                   "Pelas informações enviadas não há sinais de risco imediato. Aguarde ser chamado e não ofereça "
                   "remédios por conta própria."),
    )


def _relatorio_de(b: BriefingIA, id_formulario: int, processado_em: datetime) -> RelatorioIA:
    return RelatorioIA(
        id_formulario=id_formulario,
        resumo_estruturado=b.resumo_estruturado,
        pontos_investigacao=list(b.pontos_investigacao),
        flag_urgencia_detectada=b.flag_urgencia_detectada,
        nivel_prioridade=b.nivel_prioridade.value,
        cor_prioridade=b.cor_prioridade.value,
        traducao_semiologica=[t.model_dump() for t in b.traducao_semiologica],
        cronologia_evolucao=b.cronologia_evolucao,
        alerta_medicacao_e_bioindicadores=b.alerta_medicacao_e_bioindicadores,
        sinais_alerta_identificados=list(b.sinais_alerta_identificados),
        orientacao_preparatoria_consultorio=b.orientacao_preparatoria_consultorio,
        alerta_seguranca_tutor=b.alerta_seguranca_tutor,
        aviso_governanca_etica=b.aviso_governanca_etica,
        modelo_utilizado=MODELO_SEED,
        processado_em=processado_em,
    )


async def _obter_tutor_pet(db, id_clinica: int, tutor: tuple[str, str], pet: dict, cache: dict) -> Pet:
    chave = tutor[1]
    if chave not in cache:
        t = Tutor(id_clinica=id_clinica, nome=tutor[0], telefone=tutor[1], aceitou_termo_seguranca=False)
        db.add(t)
        await db.flush()
        p = Pet(id_tutor=t.id_tutor, **pet)
        db.add(p)
        await db.flush()
        cache[chave] = (t, p)
    return cache[chave][1]


async def _criar_consulta(db, *, id_clinica, pet, medico, status, agendada, sintomas_por_nome,
                          triagem=None, briefing=None, inicio=None, fim=None, urgencia=False,
                          tutor=None) -> None:
    c = Consulta(
        id_clinica=id_clinica, id_pet=pet.id_pet, id_medico=medico.id_medico, status=status,
        agendada_para=agendada, criada_em=agendada - timedelta(minutes=30),
        token_triagem=gerar_token_triagem(),
        token_expira_em=max(_agora(), agendada) + timedelta(hours=72),
        inicio_consulta=inicio, fim_consulta=fim,
    )
    db.add(c)
    await db.flush()
    if triagem is None:
        return
    dados = {k: v for k, v in triagem.items() if k not in ("sintomas", "minutos_atras")}
    submetido = triagem["submetido_em"]
    sintomas = [sintomas_por_nome[n] for n in triagem["sintomas"]]
    f = FormularioTriagem(
        id_consulta=c.id_consulta,
        urgencia_deterministica=any(s.alerta_urgencia for s in sintomas),
        status_ia="concluida", submetido_em=submetido, **{k: v for k, v in dados.items() if k != "submetido_em"},
    )
    f.sintomas = sintomas
    db.add(f)
    await db.flush()
    db.add(_relatorio_de(briefing, f.id_formulario, submetido + timedelta(seconds=8)))
    if tutor is not None:
        tutor.aceitou_termo_seguranca = True
        tutor.termo_aceito_em = submetido


async def _popular_agenda(db, clinica: Clinica, medicos: list[MedicoVeterinario]) -> None:
    agora = _agora()
    sintomas_por_nome = {s.nome_sintoma: s for s in (await db.execute(select(Sintoma))).scalars()}
    cache: dict = {}

    # --- Hoje ---
    for caso in _casos_do_dia():
        pet = await _obter_tutor_pet(db, clinica.id_clinica, caso["tutor"], caso["pet"], cache)
        tutor_obj = cache[caso["tutor"][1]][0]
        agendada = agora + timedelta(minutes=caso["min_agenda"])
        inicio = fim = None
        if "inicio_min_atras" in caso:
            inicio = agora - timedelta(minutes=caso["inicio_min_atras"])
            if caso["status"] == "finalizada":
                fim = inicio + timedelta(minutes=caso["duracao_min"])
        triagem = briefing = None
        if "triagem" in caso:
            triagem = dict(caso["triagem"])
            triagem["submetido_em"] = agora - timedelta(minutes=triagem["minutos_atras"])
            b = caso["briefing"]
            briefing = _briefing(
                urgencia=b["urgencia"], nivel=b["nivel"], resumo=b["resumo"], traducao=b["traducao"],
                cronologia=b["cronologia"], med_bio=b["med_bio"], sinais=b["sinais"], pontos=b["pontos"],
                orientacao=b["orientacao"], seguranca=b["seguranca"],
            )
        await _criar_consulta(
            db, id_clinica=clinica.id_clinica, pet=pet, medico=medicos[caso["medico"]], status=caso["status"],
            agendada=agendada, sintomas_por_nome=sintomas_por_nome, triagem=triagem, briefing=briefing,
            inicio=inicio, fim=fim, tutor=tutor_obj,
        )

    # --- Histórico de 14 dias (alimenta o dashboard de ROI) ---
    for i in range(18):
        p = _HISTORICO_PACIENTES[i % len(_HISTORICO_PACIENTES)]
        pet = await _obter_tutor_pet(db, clinica.id_clinica, p["tutor"], p["pet"], cache)
        tutor_obj = cache[p["tutor"][1]][0]
        dia = 1 + (i * 14) // 18
        inicio = (agora - timedelta(days=dia)).replace(hour=13 + (i % 5), minute=(i * 7) % 60, second=0)
        sem_triagem = i in _SEM_TRIAGEM
        dur = 31 if sem_triagem else _DURACOES[i]
        triagem = briefing = None
        if not sem_triagem:
            triagem = dict(
                ambiente="Apartamento", alimentacao="Ração seca", vacinacao_em_dia=True, vermifugo_em_dia=True,
                convivio_outros_animais=False,
                manejo_preventivo="Vacinas, vermífugo e antipulgas em dia (informado pelo tutor).",
                medicamento_continuo="Nenhum medicamento contínuo",
                aspecto_urina_fezes="Sem alterações relatadas", alteracao_peso_apetite="Sem alterações relatadas",
                ingestao_hidrica="Normal", tempo_evolucao="Poucos dias",
                relato_livre_tutor="Relato registrado pelo tutor antes da consulta (dado demonstrativo).",
                sintomas=p["sintomas"], submetido_em=inicio - timedelta(minutes=45),
            )
            briefing = _briefing_historico(p)
        await _criar_consulta(
            db, id_clinica=clinica.id_clinica, pet=pet, medico=medicos[0 if i % 3 else 1], status="finalizada",
            agendada=inicio - timedelta(minutes=15), sintomas_por_nome=sintomas_por_nome, triagem=triagem,
            briefing=briefing, inicio=inicio, fim=inicio + timedelta(minutes=dur), tutor=tutor_obj,
        )


async def _limpar_agenda_demo(db, id_clinica: int) -> None:
    """Remove consultas (e, em cascata, formulários/relatórios), pets e tutores — somente da clínica demo."""
    await db.execute(delete(Consulta).where(Consulta.id_clinica == id_clinica))
    ids_tutores = select(Tutor.id_tutor).where(Tutor.id_clinica == id_clinica)
    await db.execute(delete(Pet).where(Pet.id_tutor.in_(ids_tutores)))
    await db.execute(delete(Tutor).where(Tutor.id_clinica == id_clinica))


async def seed_demo(reset: bool = False, gravar_credenciais: bool = True) -> None:
    async with AsyncSessionLocal() as db:
        clinica = await db.scalar(select(Clinica).where(Clinica.cnpj == CNPJ_DEMO))
        criou_usuarios = False
        if clinica is None:
            clinica = Clinica(nome_fantasia=NOME_CLINICA_DEMO, cnpj=CNPJ_DEMO, segmento="veterinaria")
            db.add(clinica)
            await db.flush()
        else:
            clinica.nome_fantasia, clinica.segmento = NOME_CLINICA_DEMO, "veterinaria"

        medicos: list[MedicoVeterinario] = []
        for nome, crmv in (("Dra. Helena Duarte", "CRMV-SP 10001"), ("Dr. Rafael Menezes", "CRMV-SP 10002")):
            m = await db.scalar(select(MedicoVeterinario).where(
                MedicoVeterinario.id_clinica == clinica.id_clinica, MedicoVeterinario.crmv == crmv))
            if m is None:
                m = MedicoVeterinario(id_clinica=clinica.id_clinica, nome=nome, crmv=crmv)
                db.add(m)
                await db.flush()
            else:
                m.nome = nome
            medicos.append(m)

        senhas = {p: secrets.token_urlsafe(12) for p in ("recepcao", "medico", "gestor")}
        usuarios = {
            "recepcao": dict(nome="Camila (Recepção)", id_medico=None),
            "medico": dict(nome="Dra. Helena Duarte", id_medico=medicos[0].id_medico),
            "gestor": dict(nome="Dr. Marcos Vieira (Diretor Clínico)", id_medico=None),
        }
        for papel, dados in usuarios.items():
            email = f"{papel}@demo.triagem.app"
            u = await db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
            if u is None:
                db.add(Usuario(id_clinica=clinica.id_clinica, email=email, senha_hash=hash_senha(senhas[papel]),
                               papel=papel, **dados))
                criou_usuarios = True
            else:
                u.nome, u.id_medico, u.ativo = dados["nome"], dados["id_medico"], True
                if gravar_credenciais:   # mantém .demo_credentials.txt sempre consistente com o banco
                    u.senha_hash = hash_senha(senhas[papel])
        await db.flush()

        if reset:
            await _limpar_agenda_demo(db, clinica.id_clinica)
        total = await db.scalar(select(func.count(Consulta.id_consulta)).where(Consulta.id_clinica == clinica.id_clinica))
        if total:
            await db.commit()
            print("[seed] clínica demo já populada — nada a recriar (use --reset-demo para refazer a agenda de hoje).")
        else:
            await _popular_agenda(db, clinica, medicos)
            await db.commit()
            print(f"[seed] {NOME_CLINICA_DEMO}: agenda demonstrativa e histórico de 14 dias criados.")

    if gravar_credenciais:
        caminho = os.path.join(os.path.dirname(__file__), "..", ".demo_credentials.txt")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("Credenciais DEMO (geradas localmente — não commitar)\n")
            for papel, senha in senhas.items():
                f.write(f"{papel}@demo.triagem.app  |  {senha}\n")
        print("[seed] senhas demo (re)geradas. Credenciais em .demo_credentials.txt")


async def main(demo: bool, reset_demo: bool) -> None:
    await seed_sintomas()
    if demo:
        await seed_demo(reset=reset_demo)
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true")
    p.add_argument("--reset-demo", action="store_true", help="Recria a agenda/histórico da clínica demo")
    args = p.parse_args()
    asyncio.run(main(args.demo or args.reset_demo, args.reset_demo))
