"""004 — Protocolo Completo de Emergência, Logística de Resgate e Anti-Ancoragem (RN-001 v2.0).

Migração ADITIVA: apenas colunas novas (com defaults seguros para linhas existentes).
  - clinica: atendimento_24h, horario_fechamento, possui_veiculo_resgate,
             telefone_emergencia, endereco_completo
  - consulta: modalidade_emergencia, localizacao_gps_tutor
  - formulario_triagem: alerta_critico_exibido_em, ciente_risco_morte (auditoria jurídica)

Revision ID: 004_protocolo_emergencia_resgate
Revises: 003_pet_dados_clinicos
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_protocolo_emergencia_resgate"
down_revision: Union[str, None] = "003_pet_dados_clinicos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ clinica
    op.add_column("clinica", sa.Column(
        "atendimento_24h", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("clinica", sa.Column(
        "horario_fechamento", sa.String(10), nullable=False, server_default="18:00"))
    op.add_column("clinica", sa.Column(
        "possui_veiculo_resgate", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("clinica", sa.Column("telefone_emergencia", sa.String(20), nullable=True))
    op.add_column("clinica", sa.Column("endereco_completo", sa.String(300), nullable=True))

    # ------------------------------------------------------------------ consulta
    op.add_column("consulta", sa.Column("modalidade_emergencia", sa.String(40), nullable=True))
    op.add_column("consulta", sa.Column("localizacao_gps_tutor", sa.String(255), nullable=True))

    # ------------------------------------------------------------------ formulario_triagem
    op.add_column("formulario_triagem", sa.Column(
        "alerta_critico_exibido_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("formulario_triagem", sa.Column(
        "ciente_risco_morte", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("formulario_triagem", "ciente_risco_morte")
    op.drop_column("formulario_triagem", "alerta_critico_exibido_em")
    op.drop_column("consulta", "localizacao_gps_tutor")
    op.drop_column("consulta", "modalidade_emergencia")
    op.drop_column("clinica", "endereco_completo")
    op.drop_column("clinica", "telefone_emergencia")
    op.drop_column("clinica", "possui_veiculo_resgate")
    op.drop_column("clinica", "horario_fechamento")
    op.drop_column("clinica", "atendimento_24h")
