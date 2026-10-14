"""002 — Triagem Pré-Consulta v2: multi-tenant direto, link único, contrato rico de IA.

Migração ADITIVA e segura para bancos com dados:
  - colunas novas NOT NULL são criadas nullable, preenchidas (backfill) e só então travadas;
  - nada é removido; apenas pontos_investigacao muda de Text para JSONB (com conversão).

Revision ID: 002_triagem_v2
Revises: 001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_triagem_v2"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ clinica
    op.add_column(
        "clinica",
        sa.Column("segmento", sa.String(20), nullable=False, server_default="veterinaria"),
    )

    # ------------------------------------------------------------------ usuario (novo)
    op.create_table(
        "usuario",
        sa.Column("id_usuario", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "id_clinica",
            sa.Integer(),
            sa.ForeignKey("clinica.id_clinica", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "id_medico",
            sa.Integer(),
            sa.ForeignKey("medico_veterinario.id_medico", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("papel", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_usuario_id_clinica", "usuario", ["id_clinica"])

    # ------------------------------------------------------------------ tutor
    op.add_column("tutor", sa.Column("termo_aceito_em", sa.DateTime(timezone=True), nullable=True))

    # ------------------------------------------------------------------ sintoma
    op.add_column(
        "sintoma", sa.Column("categoria", sa.String(60), nullable=False, server_default="Geral")
    )
    op.add_column(
        "sintoma", sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true")
    )

    # ------------------------------------------------------------------ consulta
    op.add_column("consulta", sa.Column("id_clinica", sa.Integer(), nullable=True))
    op.add_column("consulta", sa.Column("agendada_para", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "consulta",
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("consulta", sa.Column("token_triagem", sa.String(64), nullable=True))
    op.add_column("consulta", sa.Column("token_expira_em", sa.DateTime(timezone=True), nullable=True))

    # Backfill de consultas pré-existentes
    op.execute(
        """
        UPDATE consulta c
           SET id_clinica = m.id_clinica
          FROM medico_veterinario m
         WHERE m.id_medico = c.id_medico
        """
    )
    op.execute(
        """
        UPDATE consulta
           SET token_triagem = md5(random()::text || clock_timestamp()::text || id_consulta::text)
                            || md5(random()::text || id_consulta::text || clock_timestamp()::text),
               token_expira_em = now() + interval '72 hours'
         WHERE token_triagem IS NULL
        """
    )

    op.alter_column("consulta", "id_clinica", nullable=False)
    op.alter_column("consulta", "token_triagem", nullable=False)
    op.alter_column("consulta", "token_expira_em", nullable=False)
    op.create_foreign_key(
        "fk_consulta_clinica", "consulta", "clinica", ["id_clinica"], ["id_clinica"], ondelete="CASCADE"
    )
    op.create_index("ix_consulta_token_triagem", "consulta", ["token_triagem"], unique=True)
    op.create_index("ix_consulta_clinica_status", "consulta", ["id_clinica", "status"])
    op.create_index("ix_consulta_clinica_agendada", "consulta", ["id_clinica", "agendada_para"])

    # ------------------------------------------------------------------ formulario_triagem
    op.add_column(
        "formulario_triagem",
        sa.Column("ingestao_hidrica", sa.String(300), nullable=False, server_default="Não informado"),
    )
    op.add_column(
        "formulario_triagem",
        sa.Column("urgencia_deterministica", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "formulario_triagem",
        sa.Column("status_ia", sa.String(20), nullable=False, server_default="pendente"),
    )
    # medicamento_continuo: sem default no modelo (RN-002); coluna já era NOT NULL

    # ------------------------------------------------------------------ relatorio_ia
    op.execute(
        """
        ALTER TABLE relatorio_ia
        ALTER COLUMN pontos_investigacao TYPE jsonb
        USING CASE
            WHEN pontos_investigacao IS NULL OR pontos_investigacao = '' THEN '[]'::jsonb
            ELSE jsonb_build_array(pontos_investigacao)
        END
        """
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("nivel_prioridade", sa.String(20), nullable=False, server_default="NAO_URGENTE"),
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("cor_prioridade", sa.String(10), nullable=False, server_default="AZUL"),
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("traducao_semiologica", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "relatorio_ia", sa.Column("cronologia_evolucao", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("alerta_medicacao_e_bioindicadores", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("sinais_alerta_identificados", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "relatorio_ia",
        sa.Column("orientacao_preparatoria_consultorio", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "relatorio_ia", sa.Column("alerta_seguranca_tutor", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "relatorio_ia", sa.Column("aviso_governanca_etica", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "relatorio_ia", sa.Column("modelo_utilizado", sa.String(80), nullable=False, server_default="")
    )


def downgrade() -> None:
    for coluna in (
        "modelo_utilizado", "aviso_governanca_etica", "alerta_seguranca_tutor",
        "orientacao_preparatoria_consultorio", "sinais_alerta_identificados",
        "alerta_medicacao_e_bioindicadores", "cronologia_evolucao",
        "traducao_semiologica", "cor_prioridade", "nivel_prioridade",
    ):
        op.drop_column("relatorio_ia", coluna)
    op.execute(
        "ALTER TABLE relatorio_ia ALTER COLUMN pontos_investigacao TYPE text "
        "USING COALESCE(pontos_investigacao #>> '{0}', '')"
    )

    op.drop_column("formulario_triagem", "status_ia")
    op.drop_column("formulario_triagem", "urgencia_deterministica")
    op.drop_column("formulario_triagem", "ingestao_hidrica")

    op.drop_index("ix_consulta_clinica_agendada", table_name="consulta")
    op.drop_index("ix_consulta_clinica_status", table_name="consulta")
    op.drop_index("ix_consulta_token_triagem", table_name="consulta")
    op.drop_constraint("fk_consulta_clinica", "consulta", type_="foreignkey")
    for coluna in ("token_expira_em", "token_triagem", "criada_em", "agendada_para", "id_clinica"):
        op.drop_column("consulta", coluna)

    op.drop_column("sintoma", "ativo")
    op.drop_column("sintoma", "categoria")
    op.drop_column("tutor", "termo_aceito_em")

    op.drop_index("ix_usuario_id_clinica", table_name="usuario")
    op.drop_table("usuario")
    op.drop_column("clinica", "segmento")

