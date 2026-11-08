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


# RN-001 v2.0 — logística de emergência acionada pelo tutor
ModalidadeEmergencia = Literal["EMERGENCIA_A_CAMINHO", "RESGATE_SOLICITADO"]


def _limpa_localizacao(v: Optional[str]) -> Optional[str]:
    """Remove caracteres de controle e espaços; string vazia vira None."""
    if v is None:
        return None
    v = re.sub(r"[\x00-\x1f\x7f]", " ", v).strip()
    return v or None


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
    # Dados clínicos veterinários (opcionais)
    peso_kg: Optional[float] = Field(default=None, gt=0, le=250)
    porte: Optional[Literal["Mini", "Pequeno", "Médio", "Grande", "Gigante"]] = None
    status_reprodutivo: Optional[Literal["Castrado", "Inteiro"]] = None


class PetResumoOut(_Orm):
    nome: str
    especie: str
    raca: str
    sexo: str
    idade_texto: str
    peso_kg: Optional[float] = None
    porte: Optional[str] = None
    status_reprodutivo: Optional[str] = None


class TutorComPetsOut(BaseModel):
    nome: str
    telefone: str
    pets: list[PetResumoOut]


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
    pet_raca: str = ""
    pet_sexo: str = ""
    pet_idade: str = ""
    pet_peso_kg: Optional[float] = None
    pet_porte: Optional[str] = None
    pet_status_reprodutivo: Optional[str] = None
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
    # RN-001 v2.0 — topo da fila: paciente em deslocamento ou resgate solicitado
    modalidade_emergencia: Optional[str] = None
    localizacao_gps_tutor: Optional[str] = None
    maps_url_tutor: Optional[str] = None
    ciente_risco_morte: bool = False


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
    peso_kg: Optional[float] = None
    porte: Optional[str] = None
    status_reprodutivo: Optional[str] = None


class SintomaPublicoOut(_Orm):
    id_sintoma: int
    nome_sintoma: str
    alerta_urgencia: bool
    categoria: str
    # RN-001 v2.0: chave do "O que NÃO fazer" aplicável (INTOXICACAO, NEUROLOGICO, DISPNEIA, ...)
    categoria_emergencia: Optional[str] = None


class ProtocoloEmergenciaPublicoOut(BaseModel):
    """Dados que o frontend do tutor precisa para o Disjuntor de Emergência (RN-001 v2.0)."""

    atendimento_24h: bool
    clinica_aberta_agora: bool
    horario_fechamento: str
    possui_veiculo_resgate: bool
    whatsapp_plantao: Optional[str] = None      # telefone de plantão (sem o termo "telefone": rota pública)
    endereco_completo: Optional[str] = None
    url_hospital_24h: str
    rota_clinica: dict[str, str]
    primeiros_socorros_negativos: dict[str, str]
    gatilhos_texto: list[dict[str, str]]


class TriagemContextoOut(BaseModel):
    clinica_nome: str
    segmento: str
    tutor_primeiro_nome: str
    pet: PetPublicoOut
    agendada_para: Optional[datetime]
    estado: Literal["aguardando", "preenchida", "expirada", "cancelada"]
    sintomas: list[SintomaPublicoOut]
    texto_termo: str
    emergencia: ProtocoloEmergenciaPublicoOut
    modalidade_emergencia: Optional[str] = None


class TriagemSubmissao(BaseModel):
    aceite_termo: bool
    ambiente: str = Field(..., min_length=2, max_length=100)
    alimentacao: str = Field(..., min_length=2, max_length=200)
    vacinacao_em_dia: bool
    vermifugo_em_dia: bool
    convivio_outros_animais: bool
    # Detalhes veterinários opcionais (vacinas, vermífugo, ectoparasitas, acesso à rua, contactantes)
    manejo_preventivo: Optional[str] = Field(default=None, max_length=500)
    # RN-002 — obrigatório e explícito ("Nenhum" deve ser informado pelo tutor)
    medicamento_continuo: str = Field(..., min_length=2, max_length=500)
    aspecto_urina_fezes: str = Field(..., min_length=2, max_length=300)
    alteracao_peso_apetite: str = Field(..., min_length=2, max_length=300)
    ingestao_hidrica: str = Field(..., min_length=2, max_length=300)
    tempo_evolucao: str = Field(..., min_length=1, max_length=100)
    relato_livre_tutor: str = Field(..., min_length=10, max_length=4000)
    sintoma_ids: list[int] = Field(default_factory=list, max_length=60)
    # RN-001 v2.0 — auditoria jurídica e logística de emergência (todos opcionais)
    ciente_risco_morte: bool = False
    alerta_critico_exibido_em: Optional[datetime] = None
    modalidade_emergencia: Optional[ModalidadeEmergencia] = None
    localizacao_gps_tutor: Optional[str] = Field(default=None, max_length=255)

    @field_validator("localizacao_gps_tutor")
    @classmethod
    def _loc(cls, v: Optional[str]) -> Optional[str]:
        return _limpa_localizacao(v)

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
    # RN-001 v2.0: "O que NÃO fazer em casa" e logística de emergência registrada
    primeiros_socorros_negativos: dict[str, str] = {}
    termos_criticos_relato: list[str] = []
    modalidade_emergencia: Optional[str] = None
    maps_url_tutor: Optional[str] = None
    whatsapp_resgate_url: Optional[str] = None


class ResultadoTutorOut(BaseModel):
    status_ia: Literal["pendente", "concluida", "falhou"]
    urgencia_detectada: bool
    acao_recomendada: Literal["PRONTO_SOCORRO_IMEDIATO", "AGUARDAR_ATENDIMENTO"]
    alerta_seguranca_tutor: Optional[str] = None
    nivel_prioridade: Optional[str] = None
    primeiros_socorros_negativos: dict[str, str] = {}
    modalidade_emergencia: Optional[str] = None


class AcionarEmergenciaIn(BaseModel):
    """Tutor clicou em 'Estou a Caminho' ou 'Solicitar Veículo de Resgate da Clínica'."""

    modalidade: ModalidadeEmergencia
    localizacao_gps_tutor: Optional[str] = Field(default=None, max_length=255)
    ciente_risco_morte: bool = False
    alerta_critico_exibido_em: Optional[datetime] = None
    categorias_emergencia: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("localizacao_gps_tutor")
    @classmethod
    def _loc(cls, v: Optional[str]) -> Optional[str]:
        return _limpa_localizacao(v)

    @model_validator(mode="after")
    def _resgate_exige_localizacao(self) -> "AcionarEmergenciaIn":
        if self.modalidade == "RESGATE_SOLICITADO" and (
            not self.localizacao_gps_tutor or len(self.localizacao_gps_tutor) < 5
        ):
            raise ValueError(
                "Para solicitar o veículo de resgate, informe sua localização (GPS ou endereço)."
            )
        return self


class AcionarEmergenciaOut(BaseModel):
    registrada: bool = True
    modalidade_emergencia: ModalidadeEmergencia
    localizacao_gps_tutor: Optional[str] = None
    maps_url_tutor: Optional[str] = None
    whatsapp_resgate_url: Optional[str] = None      # wa.me do plantão (só no resgate)
    rota_clinica: dict[str, str]                    # Google Maps/Waze até a clínica
    whatsapp_plantao: Optional[str] = None
    primeiros_socorros_negativos: dict[str, str]
    mensagem_para_tutor: str


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
    manejo_preventivo: Optional[str] = None
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
    peso_kg: Optional[float] = None
    porte: Optional[str] = None
    status_reprodutivo: Optional[str] = None


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
    # RN-001 v2.0 — status de deslocamento/resgate e Protocolo Anti-Ancoragem (ABC de Emergência)
    modalidade_emergencia: Optional[str] = None
    localizacao_gps_tutor: Optional[str] = None
    maps_url_tutor: Optional[str] = None
    ciente_risco_morte: bool = False
    alerta_critico_exibido_em: Optional[datetime] = None
    protocolo_abc_emergencia: list[str] = []


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


class RiscoDistribuicaoItem(BaseModel):
    cor: str                 # VERMELHO | LARANJA | AMARELO | VERDE | AZUL (Protocolo de Manchester)
    nivel: str
    quantidade: int
    percentual: float


class MetricasOut(RoiOut):
    """Dashboard executivo B2B: ROI + receita potencial + distribuição de risco Manchester."""

    ticket_medio_consulta: float
    receita_adicional_potencial: float
    distribuicao_risco: list[RiscoDistribuicaoItem]
    emergencias_acionadas: int
    resgates_solicitados: int
