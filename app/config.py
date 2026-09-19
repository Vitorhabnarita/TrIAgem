"""
config.py — Configurações da aplicação via Pydantic Settings.
Lê variáveis de ambiente ou do arquivo .env na raiz do projeto.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -----------------------------------------------------------------------
    # Banco de dados
    # -----------------------------------------------------------------------
    # Formato asyncpg: postgresql+asyncpg://user:password@host:port/dbname
    database_url: str = "postgresql+asyncpg://triagem:triagem@localhost:5432/triagem_db"

    # Configurações do pool de conexões
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False       # True exibe SQL bruto no console

    # -----------------------------------------------------------------------
    # Aplicação
    # -----------------------------------------------------------------------
    app_name: str = "TrIAgem API"
    app_version: str = "0.1.0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()

