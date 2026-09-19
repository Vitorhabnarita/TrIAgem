"""
schemas.py — Schemas Pydantic para validação de entrada/saída da API TrIAgem.

Convenção de nomenclatura:
  - <Model>Base   : campos comuns compartilhados
  - <Model>Create : payload de criação (POST) — sem id nem campos automáticos
  - <Model>Update : payload de atualização parcial (PATCH) — todos os campos opcionais
  - <Model>Out    : resposta da API (GET) — inclui id e campos gerados pelo banco
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===========================================================================
# Configuração comum para schemas de saída (ORM mode)
# ===========================================================================

class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# 1. Clinica
# ===========================================================================

class ClinicaBase(BaseModel):
    nome_fantasia: str = Field(..., max_length=255, examples=["PetCare Veterinária"])
    cnpj: str = Field(..., max_length=18, examples=["12.345.678/0001-90"])
    ativa: bool = Field(default=True)

    @field_validator("cnpj")
    @classmethod
    def cnpj_format(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos numéricos.")
        return v


class ClinicaCreate(ClinicaBase):
    pass


class ClinicaUpdate(BaseModel):
    nome_fantasia: Optional[str] = Field(None, max_length=255)
    cnpj: Optional[str] = Field(None, max_length=18)
    ativa: Optional[bool] = None


class ClinicaOut(_OrmBase, ClinicaBase):
    id_clinica: int


# ===========================================================================
# 2. MedicoVeterinario
# ===========================================================================

class MedicoVeterinarioBase(BaseModel):
    id_clinica: int = Field(..., gt=0)
    nome: str = Field(..., max_length=255, examples=["Dr. João Silva"])
    crmv: str = Field(..., max_length=20, examples=["CRMV-SP 12345"])


class MedicoVeterinarioCreate(MedicoVeterinarioBase):
    pass


class MedicoVeterinarioUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=255)
    crmv: Optional[str] = Field(None, max_length=20)


class MedicoVeterinarioOut(_OrmBase, MedicoVeterinarioBase):
    id_medico: int


# ===========================================================================
# 3. Tutor
# ===========================================================================

class TutorBase(BaseModel):
    id_clinica: int = Field(..., gt=0)
    nome: str = Field(..., max_length=255, examples=["Maria Oliveira"])
    telefone: str = Field(..., max_length=20, examples=["(11) 99999-8888"])
    aceitou_termo_seguranca: bool = Field(default=False)


class TutorCreate(TutorBase):
    pass


class TutorUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=255)
    telefone: Optional[str] = Field(None, max_length=20)
    aceitou_termo_seguranca: Optional[bool] = None


class TutorOut(_OrmBase, TutorBase):
    id_tutor: int


# ===========================================================================
# 4. Pet
# ===========================================================================

class PetBase(BaseModel):
    id_tutor: int = Field(..., gt=0)
    nome: str = Field(..., max_length=100, examples=["Bolinha"])
    especie: str = Field(..., max_length=50, examples=["Cão"])
    raca: str = Field(..., max_length=100, examples=["Labrador"])
    sexo: str = Field(..., max_length=15, examples=["Macho"])
    idade_texto: str = Field(..., max_length=50, examples=["3 anos"])

    @field_validator("sexo")
    @classmethod
    def sexo_valido(cls, v: str) -> str:
        permitidos = {"Macho", "Fêmea", "Não informado"}
        if v not in permitidos:
            raise ValueError(f"sexo deve ser um de: {', '.join(permitidos)}")
        return v


class PetCreate(PetBase):
    pass


class PetUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=100)
    especie: Optional[str] = Field(None, max_length=50)
    raca: Optional[str] = Field(None, max_length=100)
    sexo: Optional[str] = Field(None, max_length=15)
    idade_texto: Optional[str] = Field(None, max_length=50)


class PetOut(_OrmBase, PetBase):
    id_pet: int


# ===========================================================================
# 5. Consulta
# ===========================================================================

CONSULTA_STATUS_VALIDOS = {"agendada", "em_andamento", "finalizada", "cancelada"}


class ConsultaBase(BaseModel):
    id_pet: int = Field(..., gt=0)
    id_medico: int = Field(..., gt=0)
    status: str = Field(default="agendada", examples=["agendada"])
    inicio_consulta: Optional[datetime] = None
    fim_consulta: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def status_valido(cls, v: str) -> str:
        if v not in CONSULTA_STATUS_VALIDOS:
            raise ValueError(f"status deve ser um de: {', '.join(sorted(CONSULTA_STATUS_VALIDOS))}")
        return v


class ConsultaCreate(ConsultaBase):
    pass


class ConsultaUpdate(BaseModel):
    status: Optional[str] = None
    inicio_consulta: Optional[datetime] = None
    fim_consulta: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def status_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CONSULTA_STATUS_VALIDOS:
            raise ValueError(f"status deve ser um de: {', '.join(sorted(CONSULTA_STATUS_VALIDOS))}")
        return v


class ConsultaOut(_OrmBase, ConsultaBase):
    id_consulta: int


# ===========================================================================
# 6. Sintoma
# ===========================================================================

class SintomaBase(BaseModel):
    nome_sintoma: str = Field(..., max_length=200, examples=["Vômito frequente"])
    alerta_urgencia: bool = Field(default=False)


class SintomaCreate(SintomaBase):
    pass


class SintomaUpdate(BaseModel):
    nome_sintoma: Optional[str] = Field(None, max_length=200)
    alerta_urgencia: Optional[bool] = None


class SintomaOut(_OrmBase, SintomaBase):
    id_sintoma: int


# ===========================================================================
# 7. FormularioTriagem
# ===========================================================================

class FormularioTriagemBase(BaseModel):
    id_consulta: int = Field(..., gt=0)
    ambiente: str = Field(..., max_length=100, examples=["Apartamento"])
    alimentacao: str = Field(..., max_length=200, examples=["Ração premium"])
    vacinacao_em_dia: bool = Field(default=False)
    vermifugo_em_dia: bool = Field(default=False)
    convivio_outros_animais: bool = Field(default=False)
    medicamento_continuo: str = Field(default="Nenhum", max_length=500)
    aspecto_urina_fezes: str = Field(..., max_length=300, examples=["Normal"])
    alteracao_peso_apetite: str = Field(..., max_length=300, examples=["Sem alteração"])
    tempo_evolucao: str = Field(..., max_length=100, examples=["2 dias"])
    relato_livre_tutor: str = Field(..., examples=["Pet apresentou prostração e recusa alimentar."])


class FormularioTriagemCreate(FormularioTriagemBase):
    """Payload de criação. sintoma_ids associa sintomas ao formulário (N:N)."""
    sintoma_ids: List[int] = Field(default_factory=list, examples=[[1, 3]])


class FormularioTriagemUpdate(BaseModel):
    ambiente: Optional[str] = Field(None, max_length=100)
    alimentacao: Optional[str] = Field(None, max_length=200)
    vacinacao_em_dia: Optional[bool] = None
    vermifugo_em_dia: Optional[bool] = None
    convivio_outros_animais: Optional[bool] = None
    medicamento_continuo: Optional[str] = Field(None, max_length=500)
    aspecto_urina_fezes: Optional[str] = Field(None, max_length=300)
    alteracao_peso_apetite: Optional[str] = Field(None, max_length=300)
    tempo_evolucao: Optional[str] = Field(None, max_length=100)
    relato_livre_tutor: Optional[str] = None
    sintoma_ids: Optional[List[int]] = None


class FormularioTriagemOut(_OrmBase, FormularioTriagemBase):
    id_formulario: int
    submetido_em: datetime
    sintomas: List[SintomaOut] = []


# ===========================================================================
# 8. RelatorioIA
# ===========================================================================

class RelatorioIABase(BaseModel):
    id_formulario: int = Field(..., gt=0)
    resumo_estruturado: str = Field(..., examples=["Pet apresenta sinais compatíveis com gastroenterite."])
    pontos_investigacao: str = Field(..., examples=["Verificar hidratação. Solicitar hemograma."])
    flag_urgencia_detectada: bool = Field(default=False)


class RelatorioIACreate(RelatorioIABase):
    pass


class RelatorioIAUpdate(BaseModel):
    resumo_estruturado: Optional[str] = None
    pontos_investigacao: Optional[str] = None
    flag_urgencia_detectada: Optional[bool] = None


class RelatorioIAOut(_OrmBase, RelatorioIABase):
    id_relatorio: int
    processado_em: datetime


# ===========================================================================
# Schemas compostos (respostas ricas / nested)
# ===========================================================================

class PetComTutorOut(_OrmBase):
    """Pet com dados básicos do tutor (usado em consultas detalhadas)."""
    id_pet: int
    nome: str
    especie: str
    raca: str
    sexo: str
    idade_texto: str
    tutor: TutorOut


class ConsultaDetalhadaOut(_OrmBase):
    """Consulta completa com pet, médico, formulário e relatório."""
    id_consulta: int
    status: str
    inicio_consulta: Optional[datetime]
    fim_consulta: Optional[datetime]
    pet: PetOut
    medico: MedicoVeterinarioOut
    formulario: Optional[FormularioTriagemOut] = None
    relatorio: Optional[RelatorioIAOut] = None

