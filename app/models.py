"""
models.py — SQLAlchemy ORM models para o sistema B2B TrIAgem.
Arquitetura multi-tenant: cada clínica possui isolamento de dados via
chaves estrangeiras aninhadas (clinica → medico/tutor → pet → consulta).
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


# ---------------------------------------------------------------------------
# Base declarativa
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Base comum para todos os modelos ORM."""
    pass


# ---------------------------------------------------------------------------
# 1. Clinica — raiz do tenant
# ---------------------------------------------------------------------------

class Clinica(Base):
    """
    Representa uma clínica veterinária (tenant).
    Todos os dados de negócio são subordinados a esta entidade.
    """

    __tablename__ = "clinica"

    id_clinica: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_fantasia: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(18), nullable=False, unique=True)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relacionamentos
    medicos: Mapped[List["MedicoVeterinario"]] = relationship(
        "MedicoVeterinario", back_populates="clinica", cascade="all, delete-orphan"
    )
    tutores: Mapped[List["Tutor"]] = relationship(
        "Tutor", back_populates="clinica", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Clinica id={self.id_clinica} nome='{self.nome_fantasia}'>"


# ---------------------------------------------------------------------------
# 2. MedicoVeterinario
# ---------------------------------------------------------------------------

class MedicoVeterinario(Base):
    """
    Médico veterinário vinculado a uma clínica (tenant).
    O CRMV é único dentro do escopo de cada clínica.
    """

    __tablename__ = "medico_veterinario"

    __table_args__ = (
        UniqueConstraint("id_clinica", "crmv", name="uq_medico_clinica_crmv"),
    )

    id_medico: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_clinica: Mapped[int] = mapped_column(
        Integer, ForeignKey("clinica.id_clinica", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    crmv: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relacionamentos
    clinica: Mapped["Clinica"] = relationship("Clinica", back_populates="medicos")
    consultas: Mapped[List["Consulta"]] = relationship(
        "Consulta", back_populates="medico"
    )

    def __repr__(self) -> str:
        return f"<MedicoVeterinario id={self.id_medico} nome='{self.nome}' crmv='{self.crmv}'>"


# ---------------------------------------------------------------------------
# 3. Tutor
# ---------------------------------------------------------------------------

class Tutor(Base):
    """
    Tutor (dono) do pet. Isolado por clínica para garantir privacidade de dados
    entre diferentes tenants (LGPD/multi-tenant).
    """

    __tablename__ = "tutor"

    id_tutor: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_clinica: Mapped[int] = mapped_column(
        Integer, ForeignKey("clinica.id_clinica", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    aceitou_termo_seguranca: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Relacionamentos
    clinica: Mapped["Clinica"] = relationship("Clinica", back_populates="tutores")
    pets: Mapped[List["Pet"]] = relationship(
        "Pet", back_populates="tutor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tutor id={self.id_tutor} nome='{self.nome}'>"


# ---------------------------------------------------------------------------
# 4. Pet
# ---------------------------------------------------------------------------

class Pet(Base):
    """
    Animal de estimação pertencente a um tutor.
    A idade é armazenada como texto (ex: '2 anos', '6 meses') para flexibilidade
    de entrada pelo tutor na triagem.
    """

    __tablename__ = "pet"

    id_pet: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_tutor: Mapped[int] = mapped_column(
        Integer, ForeignKey("tutor.id_tutor", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    especie: Mapped[str] = mapped_column(String(50), nullable=False)   # ex: Cão, Gato
    raca: Mapped[str] = mapped_column(String(100), nullable=False)
    sexo: Mapped[str] = mapped_column(String(15), nullable=False)      # Macho / Fêmea / Não informado
    idade_texto: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relacionamentos
    tutor: Mapped["Tutor"] = relationship("Tutor", back_populates="pets")
    consultas: Mapped[List["Consulta"]] = relationship(
        "Consulta", back_populates="pet", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Pet id={self.id_pet} nome='{self.nome}' especie='{self.especie}'>"


# ---------------------------------------------------------------------------
# 5. Consulta
# ---------------------------------------------------------------------------

class Consulta(Base):
    """
    Registro de uma consulta veterinária.
    Início e fim permitem medir o tempo gasto no consultório.
    Status controla o fluxo: agendada → em_andamento → finalizada.
    """

    __tablename__ = "consulta"

    id_consulta: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_pet: Mapped[int] = mapped_column(
        Integer, ForeignKey("pet.id_pet", ondelete="RESTRICT"), nullable=False
    )
    id_medico: Mapped[int] = mapped_column(
        Integer, ForeignKey("medico_veterinario.id_medico", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="agendada"
    )  # agendada | em_andamento | finalizada
    inicio_consulta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fim_consulta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relacionamentos
    pet: Mapped["Pet"] = relationship("Pet", back_populates="consultas")
    medico: Mapped["MedicoVeterinario"] = relationship("MedicoVeterinario", back_populates="consultas")
    formulario: Mapped[Optional["FormularioTriagem"]] = relationship(
        "FormularioTriagem", back_populates="consulta", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Consulta id={self.id_consulta} status='{self.status}'>"


# ---------------------------------------------------------------------------
# 6. Sintoma — catálogo global de sintomas
# ---------------------------------------------------------------------------

class Sintoma(Base):
    """
    Catálogo de sintomas conhecidos.
    alerta_urgencia sinaliza sintomas que requerem atendimento imediato.
    """

    __tablename__ = "sintoma"

    id_sintoma: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_sintoma: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    alerta_urgencia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relacionamentos N:N
    formularios: Mapped[List["FormularioTriagem"]] = relationship(
        "FormularioTriagem",
        secondary="formulario_sintoma",
        back_populates="sintomas",
    )

    def __repr__(self) -> str:
        return f"<Sintoma id={self.id_sintoma} nome='{self.nome_sintoma}' urgencia={self.alerta_urgencia}>"


# ---------------------------------------------------------------------------
# 7. FormularioTriagem
# ---------------------------------------------------------------------------

class FormularioTriagem(Base):
    """
    Formulário de triagem preenchido pelo tutor antes/durante a consulta.
    Captura informações clínicas e de estilo de vida do pet para alimentar a IA.
    """

    __tablename__ = "formulario_triagem"

    id_formulario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_consulta: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("consulta.id_consulta", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 com consulta
    )
    ambiente: Mapped[str] = mapped_column(String(100), nullable=False)          # ex: Apartamento, Casa c/ quintal
    alimentacao: Mapped[str] = mapped_column(String(200), nullable=False)       # ex: Ração premium, Caseira
    vacinacao_em_dia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vermifugo_em_dia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    convivio_outros_animais: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    medicamento_continuo: Mapped[str] = mapped_column(String(500), nullable=False, default="Nenhum")
    aspecto_urina_fezes: Mapped[str] = mapped_column(String(300), nullable=False)
    alteracao_peso_apetite: Mapped[str] = mapped_column(String(300), nullable=False)
    tempo_evolucao: Mapped[str] = mapped_column(String(100), nullable=False)    # ex: 2 dias, 1 semana
    relato_livre_tutor: Mapped[str] = mapped_column(Text, nullable=False)
    submetido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relacionamentos
    consulta: Mapped["Consulta"] = relationship("Consulta", back_populates="formulario")
    sintomas: Mapped[List["Sintoma"]] = relationship(
        "Sintoma",
        secondary="formulario_sintoma",
        back_populates="formularios",
    )
    relatorio: Mapped[Optional["RelatorioIA"]] = relationship(
        "RelatorioIA", back_populates="formulario", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FormularioTriagem id={self.id_formulario} consulta_id={self.id_consulta}>"


# ---------------------------------------------------------------------------
# 8. FormularioSintoma — tabela de associação N:N
# ---------------------------------------------------------------------------

from sqlalchemy import Table, Column  # noqa: E402  (import localizado por clareza)

formulario_sintoma = Table(
    "formulario_sintoma",
    Base.metadata,
    Column(
        "id_formulario",
        Integer,
        ForeignKey("formulario_triagem.id_formulario", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "id_sintoma",
        Integer,
        ForeignKey("sintoma.id_sintoma", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# 9. RelatorioIA
# ---------------------------------------------------------------------------

class RelatorioIA(Base):
    """
    Relatório gerado pela IA após análise do formulário de triagem.
    flag_urgencia_detectada espelha a lógica de alerta para o médico.
    """

    __tablename__ = "relatorio_ia"

    id_relatorio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_formulario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("formulario_triagem.id_formulario", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 com formulario
    )
    resumo_estruturado: Mapped[str] = mapped_column(Text, nullable=False)
    pontos_investigacao: Mapped[str] = mapped_column(Text, nullable=False)
    flag_urgencia_detectada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relacionamentos
    formulario: Mapped["FormularioTriagem"] = relationship(
        "FormularioTriagem", back_populates="relatorio"
    )

    def __repr__(self) -> str:
        return f"<RelatorioIA id={self.id_relatorio} urgencia={self.flag_urgencia_detectada}>"

