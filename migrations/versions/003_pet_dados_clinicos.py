"""003 — Dados clínicos veterinários do Pet (peso, porte, status reprodutivo).

Migração ADITIVA: apenas colunas anuláveis; nenhum dado existente é alterado.

Revision ID: 003_pet_dados_clinicos
Revises: 002_triagem_v2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_pet_dados_clinicos"
down_revision: Union[str, None] = "002_triagem_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pet", sa.Column("peso_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column("pet", sa.Column("porte", sa.String(15), nullable=True))
    op.add_column("pet", sa.Column("status_reprodutivo", sa.String(20), nullable=True))
    op.add_column("formulario_triagem", sa.Column("manejo_preventivo", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("formulario_triagem", "manejo_preventivo")
    op.drop_column("pet", "status_reprodutivo")
    op.drop_column("pet", "porte")
    op.drop_column("pet", "peso_kg")
