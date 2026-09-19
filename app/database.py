"""
database.py — Configuração do motor assíncrono SQLAlchemy + asyncpg para PostgreSQL.

Uso básico:
    from app.database import get_db

    @app.get("/exemplo")
    async def exemplo(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Clinica))
        return result.scalars().all()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ---------------------------------------------------------------------------
# Motor assíncrono
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,          # Loga SQL no console (desative em produção)
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,             # Verifica conexões ociosas antes de usar
    pool_recycle=1800,              # Recicla conexões a cada 30 min
)

# ---------------------------------------------------------------------------
# Fábrica de sessões assíncronas
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,         # Evita lazy-load após commit em contexto async
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# Dependency do FastAPI
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Fornece uma sessão de banco de dados por requisição HTTP.
    Garante rollback automático em caso de exceção e fechamento da sessão.

    Exemplo:
        async def endpoint(db: AsyncSession = Depends(get_db)): ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Utilitário para criação de tabelas (desenvolvimento/testes)
# ---------------------------------------------------------------------------

async def create_all_tables() -> None:
    """
    Cria todas as tabelas definidas nos modelos ORM.
    Prefer usar Alembic para migrações em produção.
    Use apenas em ambiente de desenvolvimento ou testes.
    """
    from app.models import Base  # import local para evitar ciclo

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Remove todas as tabelas. USE APENAS EM AMBIENTE DE TESTES.
    """
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

