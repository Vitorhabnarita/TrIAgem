"""
schemas.py — Schemas Pydantic (validação de entrada/saída) da API TrIAgem.

Convenção:
  - <X>In / <X>Create : payloads de entrada (nunca aceitam id_clinica do cliente — RN-004)
  - <X>Out            : respostas
Vocabulário padronizado: Triagem Pré-Consulta · Relatório Clínico Prévio ·
Briefing Estruturado de Triagem · Investigação Inicial.
"""

import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v or "")


# ===========================================================================
# Autenticação
# ===========================================================================

class LoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(..., min_length=1, max_length=128)


class UsuarioOut(_Orm):
    id_usuario: int
    nome: str
    email: str
    papel: str
    id_clinica: int
    id_medico: Optional[int] = None


class ClinicaResumoOut(_Orm):
    id_clinica: int
    nome_fantasia: str
    segmento: str


class SessaoOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    usuario: UsuarioOut
    clinica: ClinicaResumoOut


# ===========================================================================
# Backoffice (admin) e cadastro
# ===========================================================================

class ClinicaCreate(BaseModel):
    nome_fantasia: str = Field(..., min_length=2, max_length=255)
    cnpj: str = Field(..., max_length=18, examples=["12.345.678/0001-90"])
    segmento: Literal["veterinaria", "humana"] = "veterinaria"

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if len(_so_digitos(v)) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos numéricos.")
        return v


class ClinicaOut(_Orm):
    id_clinica: int
    nome_fantasia: str
    cnpj: str
    ativa: bool
    segmento: str


class MedicoCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    crmv: str = Field(..., min_length=3, max_length=20, examples=["CRMV-SP 12345"])

    @field_validator("crmv")
    @classmethod
    def _crmv(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v.strip().upper())


class MedicoOut(_Orm):
    id_medico: int
    id_clinica: int
    nome: str
    crmv: str


class UsuarioCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    senha: str = Field(..., min_length=10, max_length=128)
    papel: Literal["recepcao", "medico", "gestor"]
    id_medico: Optional[int] = Field(None, gt=0)

    @model_validator(mode="after")
    def _medico_exige_vinculo(self) -> "UsuarioCreate":
        if self.papel == "medico" and not self.id_medico:
            raise ValueError("Usuário com papel 'medico' precisa de id_medico.")
        return self


# ===========================================================================
# Sintomas
# ===========================================================================

class SintomaOut(_Orm):
    id_sintoma: int
    nome_sintoma: str
    alerta_urgencia: bool
    categoria: str = "Geral"


# ===========================================================================
# Agendamento / Consultas
# ===========================================================================

class TutorIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    telefone: str = Field(..., max_length=20, examples=["(11) 99999-8888"])

    @field_validator("telefone")
    @classmethod
    def _tel(cls, v: str) -> str:
        d = _so_digitos(v)
        if not 10 <= len(d) <= 13:
            raise ValueError("Telefone inválido. Informe DDD + número.")
        return d


class PetIn(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    especie: str = Field(..., min_length=2, max_length=50, examples=["Cão"])
    raca: str = Field(default="Sem raça definida", max_length=100)
    sexo: Literal["Macho", "Fêmea", "Não informado"] = "Não informado"
    idade_texto: str = Field(default="Não informada", max_length=50)


class ConsultaAgendar(BaseModel):
    """Agendamento rápido da recepção: tutor + pet são criados/reaproveitados na clínica."""

    id_medico: int = Field(..., gt=0)
    agendada_para: Optional[datetime] = None
    tutor: TutorIn
    pet: PetIn


class MedicoMini(_Orm):
    id_medico: int
    nome: str


class ConsultaFilaItem(BaseModel):
    id_consulta: int
    status: str
    agendada_para: Optional[datetime]
    pet_nome: str
    especie: str
    tutor_nome: str
    tutor_telefone: str
    medico: MedicoMini
    # pendente | preenchido | urgencia
    status_triagem: Literal["pendente", "preenchido", "urgencia"]
    urgencia: bool
    nivel_prioridade: Optional[str] = None
    cor_prioridade: Optional[str] = None
    status_ia: Optional[str] = None
    link_triagem: str
    whatsapp_url: str
    inicio_consulta: Optional[datetime] = None
    fim_consulta: Optional[datetime] = None
    duracao_minutos: Optional[float] = None
    minutos_economizados: Optional[float] = None


class ConsultaFinalizadaOut(BaseModel):
    id_consulta: int
    status: str
    inicio_consulta: datetime
    fim_consulta: datetime
    duracao_minutos: float
    benchmark_minutos: int
    minutos_economizados: float
    com_triagem: bool
    mensagem: str


class ConsultaStatusOut(_Orm):
    id_consulta: int
    status: str
    inicio_consulta: Optional[datetime] = None
    fim_consulta: Optional[datetime] = None


# ===========================================================================
# Triagem Pré-Consulta — fluxo público do tutor (via token)
# ===========================================================================

class PetPublicoOut(_Orm):
    nome: str
    especie: str
    raca: str
    sexo: str
    idade_texto: str


class SintomaPublicoOut(_Orm):
    id_sintoma: int
    nome_sintoma: str
    alerta_urgencia: bool
    categoria: str


class TriagemContextoOut(BaseModel):
    clinica_nome: str
    segmento: str
    tutor_primeiro_nome: str
    pet: PetPublicoOut
    agendada_para: Optional[datetime]
    estado: Literal["aguardando", "preenchida", "expirada", "cancelada"]
    sintomas: list[SintomaPublicoOut]
    texto_termo: str


class TriagemSubmissao(BaseModel):
    aceite_termo: bool
    ambiente: str = Field(..., min_length=2, max_length=100)
    alimentacao: str = Field(..., min_length=2, max_length=200)
    vacinacao_em_dia: bool
    vermifugo_em_dia: bool
    convivio_outros_animais: bool
    # RN-002 — obrigatório e explícito ("Nenhum" deve ser informado pelo tutor)
    medicamento_continuo: str = Field(..., min_length=2, max_length=500)
    aspecto_urina_fezes: str = Field(..., min_length=2, max_length=300)
    alteracao_peso_apetite: str = Field(..., min_length=2, max_length=300)
    ingestao_hidrica: str = Field(..., min_length=2, max_length=300)
    tempo_evolucao: str = Field(..., min_length=1, max_length=100)
    relato_livre_tutor: str = Field(..., min_length=10, max_length=4000)
    sintoma_ids: list[int] = Field(default_factory=list, max_length=60)

    @field_validator("aceite_termo")
    @classmethod
    def _termo(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "É necessário aceitar o termo de consentimento para enviar a Triagem Pré-Consulta."
            )
        return v

    @field_validator("sintoma_ids")
    @classmethod
    def _dedup(cls, v: list[int]) -> list[int]:
        return sorted(set(v))

    @field_validator(
        "ambiente", "alimentacao", "medicamento_continuo", "aspecto_urina_fezes",
        "alteracao_peso_apetite", "ingestao_hidrica", "tempo_evolucao", "relato_livre_tutor",
    )
    @classmethod
    def _strip_nao_vazio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Campo obrigatório.")
        return v


class TriagemSubmissaoOut(BaseModel):
    recebida: bool = True
    urgencia_detectada: bool
    sintomas_urgencia: list[str]
    acao_recomendada: Literal["PRONTO_SOCORRO_IMEDIATO", "AGUARDAR_ATENDIMENTO"]
    mensagem_para_tutor: str
    status_ia: str


class ResultadoTutorOut(BaseModel):
    status_ia: Literal["pendente", "concluida", "falhou"]
    urgencia_detectada: bool
    acao_recomendada: Literal["PRONTO_SOCORRO_IMEDIATO", "AGUARDAR_ATENDIMENTO"]
    alerta_seguranca_tutor: Optional[str] = None
    nivel_prioridade: Optional[str] = None


# ===========================================================================
# Painel clínico — Briefing Estruturado de Triagem
# ===========================================================================

class TraducaoOut(BaseModel):
    relato_leigo: str
    termo_tecnico_descritivo: str


class RelatorioOut(_Orm):
    id_relatorio: int
    flag_urgencia_detectada: bool
    nivel_prioridade: str
    cor_prioridade: str
    resumo_estruturado: str
    traducao_semiologica: list[TraducaoOut]
    cronologia_evolucao: str
    alerta_medicacao_e_bioindicadores: str
    sinais_alerta_identificados: list[str]
    pontos_investigacao: list[str]
    orientacao_preparatoria_consultorio: str
    alerta_seguranca_tutor: str
    aviso_governanca_etica: str
    modelo_utilizado: str
    processado_em: datetime


class FormularioOut(_Orm):
    id_formulario: int
    ambiente: str
    alimentacao: str
    vacinacao_em_dia: bool
    vermifugo_em_dia: bool
    convivio_outros_animais: bool
    medicamento_continuo: str
    aspecto_urina_fezes: str
    alteracao_peso_apetite: str
    ingestao_hidrica: str
    tempo_evolucao: str
    relato_livre_tutor: str
    urgencia_deterministica: bool
    status_ia: str
    submetido_em: datetime
    sintomas: list[SintomaOut] = []


class PacienteOut(_Orm):
    id_pet: int
    nome: str
    especie: str
    raca: str
    sexo: str
    idade_texto: str


class TutorOut(_Orm):
    id_tutor: int
    nome: str
    telefone: str


class BriefingOut(BaseModel):
    id_consulta: int
    status: str
    agendada_para: Optional[datetime]
    inicio_consulta: Optional[datetime]
    fim_consulta: Optional[datetime]
    medico: MedicoMini
    pet: PacienteOut
    tutor: TutorOut
    triagem_preenchida: bool
    formulario: Optional[FormularioOut] = None
    relatorio: Optional[RelatorioOut] = None
    # RN-001: determinístico OR semântico
    urgencia: bool
    sintomas_urgencia: list[str] = []
    status_ia: Optional[str] = None
    medicamento_continuo: Optional[str] = None
    benchmark_minutos: int


# ===========================================================================
# Dashboard de ROI (RN-003)
# ===========================================================================

class RoiSerieDia(BaseModel):
    dia: str
    consultas: int
    minutos_economizados: float


class RoiOut(BaseModel):
    de: datetime
    ate: datetime
    benchmark_minutos: int
    consultas_finalizadas: int
    consultas_com_triagem: int
    minutos_economizados: float
    horas_economizadas: float
    capacidade_extra_atendimentos: float
    duracao_media_minutos: Optional[float]
    total_agendadas: int
    triagens_realizadas: int
    taxa_adesao_pct: float
    urgencias_detectadas: int
    urgencias_pct: float
    serie_diaria: list[RoiSerieDia]
    observacao: str
