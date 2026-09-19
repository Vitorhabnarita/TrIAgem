"""
migrations/env.py — Configuração do Alembic para suporte a migrações assíncronas.

Suporta dois modos:
  - Online  : conecta ao banco e aplica migrações diretamente (padrão).
  - Offline : gera scripts SQL sem conexão ativa (útil para revisão/deploy).

Para gerar uma nova revisão:
    alembic revision --autogenerate -m "descricao_da_mudança"

Para aplicar migrações:
    alembic upgrade head

Para reverter uma migração:
    alembic downgrade -1
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Adiciona a raiz do projeto ao PYTHONPATH para importar app.*
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings   # noqa: E402
from app.models import Base       # noqa: E402  — importa todos os modelos via Base

# ---------------------------------------------------------------------------
# Configuração do Alembic
# ---------------------------------------------------------------------------
config = context.config

# Injeta a URL do banco a partir do settings (respeita .env)
# configparser interpreta % como interpolação — escapamos com %%
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# Configura logging a partir do alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata dos modelos para autogenerate
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Modo OFFLINE — gera scripts SQL sem conexão
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Gera scripts SQL sem necessidade de conexão ativa com o banco.
    Execute com: alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Renderiza tipos nativos do PostgreSQL (ex: BOOLEAN ao invés de INTEGER)
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Modo ONLINE — conecta ao banco e aplica migrações (async)
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Compara tipos de colunas para detectar mudanças de tipo
        compare_type=True,
        # Compara valores default definidos no servidor
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Cria engine assíncrono e executa migrações via asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Sem pool durante migrações
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
