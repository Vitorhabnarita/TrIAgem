"""
app/security.py — Autenticação JWT, hash de senha e autorização por papel (RN-004).

Princípios:
  - O id_clinica vem SEMPRE do token validado (nunca do body/URL) para escopar queries.
  - Recurso de outra clínica responde 404 (não 403) — não vaza a existência do dado.
  - Comparação de chaves em tempo constante (hmac.compare_digest).
"""

import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Usuario

PAPEL_RECEPCAO = "recepcao"
PAPEL_MEDICO = "medico"
PAPEL_GESTOR = "gestor"
PAPEIS_VALIDOS = {PAPEL_RECEPCAO, PAPEL_MEDICO, PAPEL_GESTOR}

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8")[:72], senha_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def _segredo_jwt() -> str:
    if len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET ausente ou curto (<32 caracteres). Defina no .env."
        )
    return settings.jwt_secret


def criar_token_acesso(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id_usuario),
        "cli": usuario.id_clinica,
        "pap": usuario.papel,
        "med": usuario.id_medico,
        "iat": agora,
        "exp": agora + timedelta(minutes=settings.jwt_expire_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, _segredo_jwt(), algorithm=settings.jwt_algorithm)


def decodificar_token(token: str) -> dict:
    return jwt.decode(
        token,
        _segredo_jwt(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "cli", "pap"]},
    )


# ---------------------------------------------------------------------------
# Dependências FastAPI
# ---------------------------------------------------------------------------

class UsuarioAtual:
    """Contexto de identidade extraído do token (sem round-trip pesado)."""

    __slots__ = ("id_usuario", "id_clinica", "papel", "id_medico", "nome")

    def __init__(self, id_usuario: int, id_clinica: int, papel: str, id_medico: int | None, nome: str):
        self.id_usuario = id_usuario
        self.id_clinica = id_clinica
        self.papel = papel
        self.id_medico = id_medico
        self.nome = nome


_NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticado ou sessão expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def usuario_atual(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: AsyncSession = Depends(get_db),
) -> UsuarioAtual:
    if cred is None:
        raise _NAO_AUTENTICADO
    try:
        dados = decodificar_token(cred.credentials)
    except jwt.PyJWTError:
        raise _NAO_AUTENTICADO from None

    # Revalida no banco: usuário desativado perde acesso imediatamente
    usuario = await db.get(Usuario, int(dados["sub"]))
    if usuario is None or not usuario.ativo or usuario.id_clinica != dados["cli"]:
        raise _NAO_AUTENTICADO
    return UsuarioAtual(
        usuario.id_usuario, usuario.id_clinica, usuario.papel, usuario.id_medico, usuario.nome
    )


def exigir_papeis(*papeis: str):
    """Fábrica de dependência: restringe a rota aos papéis informados."""

    async def _dep(user: UsuarioAtual = Depends(usuario_atual)) -> UsuarioAtual:
        if user.papel not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu perfil não tem permissão para esta operação.",
            )
        return user

    return _dep


async def exigir_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    """Protege rotas de backoffice do TrIAgem (criação de clínicas/usuários)."""
    esperado = settings.admin_api_key
    if len(esperado) < 24 or not x_admin_key or not hmac.compare_digest(x_admin_key, esperado):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Chave administrativa inválida."
        )


# ---------------------------------------------------------------------------
# Token do link único (WhatsApp)
# ---------------------------------------------------------------------------

def gerar_token_triagem() -> str:
    """256 bits de entropia, URL-safe (43 caracteres)."""
    return secrets.token_urlsafe(32)

