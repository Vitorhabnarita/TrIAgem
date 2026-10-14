"""
config.py — Configurações da aplicação via Pydantic Settings.
Lê variáveis de ambiente ou do arquivo .env na raiz do projeto.
"""

from pydantic import Field
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
    app_version: str = "0.2.0"
    debug: bool = False
    ambiente: str = "desenvolvimento"           # 'producao' desativa /docs e /redoc
    timezone_clinica: str = "America/Sao_Paulo"  # 'hoje' da fila e agrupamento diário do ROI

    # Origens permitidas no CORS (separadas por vírgula). Nunca use "*" em produção.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # URL pública do frontend — usada para montar o link único do WhatsApp
    frontend_base_url: str = "http://localhost:5173"

    # -----------------------------------------------------------------------
    # Segurança (RN-004)
    # -----------------------------------------------------------------------
    jwt_secret: str = Field(default="", repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480           # 8h — um turno de trabalho
    admin_api_key: str = Field(default="", repr=False)   # protege /admin/*
    token_triagem_validade_horas: int = 72  # validade do link do WhatsApp

    # Login 1-click da demonstração comercial (clínica demo do seed). DESLIGADO por padrão e
    # sempre inoperante quando ambiente == 'producao'. As senhas nunca vão para o frontend.
    demo_login_habilitado: bool = False

    # -----------------------------------------------------------------------
    # Google Gemini (Triagem Pré-Consulta)
    # -----------------------------------------------------------------------
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    gemini_fallback_model: str = "gemini-2.5-flash"
    gemini_timeout_segundos: int = 45

    # -----------------------------------------------------------------------
    # ROI (RN-003)
    # -----------------------------------------------------------------------
    roi_benchmark_minutos: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",             # variáveis desconhecidas no .env não derrubam a API
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
