"""
app/services/ai_schemas.py — Contrato estruturado do Briefing Estruturado de Triagem.

Este modelo Pydantic é enviado ao Gemini como `response_schema`, garantindo
saída JSON determinística, e também usado para validar a resposta.
"""

from enum import Enum

from pydantic import BaseModel, Field


class NivelPrioridade(str, Enum):
    EMERGENCIA = "EMERGENCIA"
    MUITO_URGENTE = "MUITO_URGENTE"
    URGENTE = "URGENTE"
    POUCO_URGENTE = "POUCO_URGENTE"
    NAO_URGENTE = "NAO_URGENTE"


class CorPrioridade(str, Enum):
    VERMELHO = "VERMELHO"
    LARANJA = "LARANJA"
    AMARELO = "AMARELO"
    VERDE = "VERDE"
    AZUL = "AZUL"


# Mapeamento determinístico nível → cor (a cor nunca é decidida pela IA)
COR_POR_NIVEL: dict[NivelPrioridade, CorPrioridade] = {
    NivelPrioridade.EMERGENCIA: CorPrioridade.VERMELHO,
    NivelPrioridade.MUITO_URGENTE: CorPrioridade.LARANJA,
    NivelPrioridade.URGENTE: CorPrioridade.AMARELO,
    NivelPrioridade.POUCO_URGENTE: CorPrioridade.VERDE,
    NivelPrioridade.NAO_URGENTE: CorPrioridade.AZUL,
}

AVISO_GOVERNANCA_ETICA = (
    "Este documento é um Relatório Clínico Prévio de Triagem Pré-Consulta, elaborado a partir "
    "de relato leigo do tutor e organizado por inteligência artificial. Não constitui "
    "diagnóstico, prognóstico nem prescrição, e não substitui a avaliação clínica presencial "
    "e o julgamento do médico veterinário responsável."
)


class TraducaoSemiologica(BaseModel):
    relato_leigo: str = Field(description="Trecho fiel do que o tutor disse, em linguagem leiga.")
    termo_tecnico_descritivo: str = Field(
        description="Termo semiológico DESCRITIVO equivalente (sinal clínico), sem nome de doença."
    )


class BriefingIA(BaseModel):
    flag_urgencia_detectada: bool = Field(
        description="True SOMENTE se houver sinais críticos de risco à vida no relato/checklist."
    )
    nivel_prioridade: NivelPrioridade
    cor_prioridade: CorPrioridade
    resumo_estruturado: str = Field(
        description="Síntese técnica semiológica concisa (3-6 linhas) SEM fechar diagnóstico."
    )
    traducao_semiologica: list[TraducaoSemiologica]
    cronologia_evolucao: str = Field(
        description="Linha do tempo do sintoma mais antigo ao mais recente, conforme o relato."
    )
    alerta_medicacao_e_bioindicadores: str = Field(
        description="Destaque de medicações contínuas/recentes e alterações de urina/fezes/ingestão/apetite/peso."
    )
    sinais_alerta_identificados: list[str] = Field(
        description="Red flags extraídas do checklist e do relato livre (lista vazia se não houver)."
    )
    pontos_investigacao: list[str] = Field(
        description="3 a 4 perguntas objetivas e parâmetros físicos/vitais a verificar presencialmente."
    )
    orientacao_preparatoria_consultorio: str = Field(
        description="Roteiro de orientação pré-consulta para o exame físico, sem induzir ancoragem nem prescrever."
    )
    alerta_seguranca_tutor: str = Field(
        description="Orientação em linguagem simples ao tutor: não medicar por conta própria; nível de urgência; SEM nomes de doenças."
    )
    aviso_governanca_etica: str = Field(
        default=AVISO_GOVERNANCA_ETICA,
        description="Declaração fixa de governança (sobrescrita pelo servidor).",
    )

