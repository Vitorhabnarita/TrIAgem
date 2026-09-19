"""
migrations/versions/001_initial_schema.py — Migração inicial TrIAgem.

Criação manual da migração base (sem conexão ao banco).
Em ambiente com PostgreSQL ativo, use:
    alembic revision --autogenerate -m "initial_schema"

Revisão: 001_initial
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria todas as tabelas do sistema TrIAgem na ordem correta de dependência."""

    # 1. clinica (raiz do tenant - sem FKs externas)
    op.create_table(
        "clinica",
        sa.Column("id_clinica", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome_fantasia", sa.String(length=255), nullable=False),
        sa.Column("cnpj", sa.String(length=18), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id_clinica"),
        sa.UniqueConstraint("cnpj"),
    )

    # 2. medico_veterinario (depende: clinica)
    op.create_table(
        "medico_veterinario",
        sa.Column("id_medico", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_clinica", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("crmv", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_clinica"], ["clinica.id_clinica"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_medico"),
        sa.UniqueConstraint("id_clinica", "crmv", name="uq_medico_clinica_crmv"),
    )

    # 3. tutor (depende: clinica)
    op.create_table(
        "tutor",
        sa.Column("id_tutor", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_clinica", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("telefone", sa.String(length=20), nullable=False),
        sa.Column("aceitou_termo_seguranca", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["id_clinica"], ["clinica.id_clinica"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_tutor"),
    )

    # 4. pet (depende: tutor)
    op.create_table(
        "pet",
        sa.Column("id_pet", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_tutor", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("especie", sa.String(length=50), nullable=False),
        sa.Column("raca", sa.String(length=100), nullable=False),
        sa.Column("sexo", sa.String(length=15), nullable=False),
        sa.Column("idade_texto", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_tutor"], ["tutor.id_tutor"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_pet"),
    )

    # 5. sintoma (catálogo global - sem FKs de tenant)
    op.create_table(
        "sintoma",
        sa.Column("id_sintoma", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome_sintoma", sa.String(length=200), nullable=False),
        sa.Column("alerta_urgencia", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id_sintoma"),
        sa.UniqueConstraint("nome_sintoma"),
    )

    # 6. consulta (depende: pet, medico_veterinario)
    op.create_table(
        "consulta",
        sa.Column("id_consulta", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_pet", sa.Integer(), nullable=False),
        sa.Column("id_medico", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="agendada"),
        sa.Column("inicio_consulta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fim_consulta", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_pet"], ["pet.id_pet"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["id_medico"], ["medico_veterinario.id_medico"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id_consulta"),
    )

    # 7. formulario_triagem (depende: consulta)
    op.create_table(
        "formulario_triagem",
        sa.Column("id_formulario", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_consulta", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=100), nullable=False),
        sa.Column("alimentacao", sa.String(length=200), nullable=False),
        sa.Column("vacinacao_em_dia", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vermifugo_em_dia", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("convivio_outros_animais", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("medicamento_continuo", sa.String(length=500), nullable=False, server_default="Nenhum"),
        sa.Column("aspecto_urina_fezes", sa.String(length=300), nullable=False),
        sa.Column("alteracao_peso_apetite", sa.String(length=300), nullable=False),
        sa.Column("tempo_evolucao", sa.String(length=100), nullable=False),
        sa.Column("relato_livre_tutor", sa.Text(), nullable=False),
        sa.Column(
            "submetido_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["id_consulta"], ["consulta.id_consulta"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_formulario"),
        sa.UniqueConstraint("id_consulta"),
    )

    # 8. formulario_sintoma (tabela N:N - depende: formulario_triagem, sintoma)
    op.create_table(
        "formulario_sintoma",
        sa.Column("id_formulario", sa.Integer(), nullable=False),
        sa.Column("id_sintoma", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_formulario"], ["formulario_triagem.id_formulario"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_sintoma"], ["sintoma.id_sintoma"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_formulario", "id_sintoma"),
    )

    # 9. relatorio_ia (depende: formulario_triagem)
    op.create_table(
        "relatorio_ia",
        sa.Column("id_relatorio", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_formulario", sa.Integer(), nullable=False),
        sa.Column("resumo_estruturado", sa.Text(), nullable=False),
        sa.Column("pontos_investigacao", sa.Text(), nullable=False),
        sa.Column("flag_urgencia_detectada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "processado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["id_formulario"], ["formulario_triagem.id_formulario"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_relatorio"),
        sa.UniqueConstraint("id_formulario"),
    )

    # Índices para performance em consultas comuns
    op.create_index("ix_medico_clinica", "medico_veterinario", ["id_clinica"])
    op.create_index("ix_tutor_clinica", "tutor", ["id_clinica"])
    op.create_index("ix_pet_tutor", "pet", ["id_tutor"])
    op.create_index("ix_consulta_pet", "consulta", ["id_pet"])
    op.create_index("ix_consulta_medico", "consulta", ["id_medico"])
    op.create_index("ix_consulta_status", "consulta", ["status"])
    op.create_index("ix_relatorio_urgencia", "relatorio_ia", ["flag_urgencia_detectada"])


def downgrade() -> None:
    """Remove todas as tabelas na ordem inversa de dependência."""
    op.drop_index("ix_relatorio_urgencia", table_name="relatorio_ia")
    op.drop_index("ix_consulta_status", table_name="consulta")
    op.drop_index("ix_consulta_medico", table_name="consulta")
    op.drop_index("ix_consulta_pet", table_name="consulta")
    op.drop_index("ix_pet_tutor", table_name="pet")
    op.drop_index("ix_tutor_clinica", table_name="tutor")
    op.drop_index("ix_medico_clinica", table_name="medico_veterinario")

    op.drop_table("relatorio_ia")
    op.drop_table("formulario_sintoma")
    op.drop_table("formulario_triagem")
    op.drop_table("consulta")
    op.drop_table("sintoma")
    op.drop_table("pet")
    op.drop_table("tutor")
    op.drop_table("medico_veterinario")
    op.drop_table("clinica")

