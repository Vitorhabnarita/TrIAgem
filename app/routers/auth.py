"""
app/routers/auth.py — Login (JWT) e identidade do usuário logado.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Clinica, Usuario
from app.ratelimit import limitar
from app.schemas import ClinicaResumoOut, LoginIn, SessaoOut, UsuarioOut
from app.security import (
    UsuarioAtual,
    criar_token_acesso,
    hash_senha,
    usuario_atual,
    verificar_senha,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Hash de referência: garante tempo similar quando o e-mail não existe (anti-enumeração)
_HASH_FALSO = hash_senha("senha-falsa-para-tempo-constante")

_CREDENCIAIS_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos."
)


@router.post(
    "/login",
    response_model=SessaoOut,
    summary="Login de recepção, médico ou gestor",
    dependencies=[Depends(limitar("login", maximo=10, janela_segundos=60))],
)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)) -> SessaoOut:
    usuario = await db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == payload.email.lower())
    )
    hash_alvo = usuario.senha_hash if usuario else _HASH_FALSO
    senha_ok = verificar_senha(payload.senha, hash_alvo)
    if usuario is None or not senha_ok or not usuario.ativo:
        raise _CREDENCIAIS_INVALIDAS

    clinica = await db.get(Clinica, usuario.id_clinica)
    if clinica is None or not clinica.ativa:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Clínica inativa. Contate o suporte.")

    return SessaoOut(
        access_token=criar_token_acesso(usuario),
        usuario=UsuarioOut.model_validate(usuario),
        clinica=ClinicaResumoOut.model_validate(clinica),
    )


@router.get("/me", response_model=UsuarioOut, summary="Usuário autenticado")
async def me(
    user: UsuarioAtual = Depends(usuario_atual), db: AsyncSession = Depends(get_db)
) -> UsuarioOut:
    usuario = await db.get(Usuario, user.id_usuario)
    return UsuarioOut.model_validate(usuario)
