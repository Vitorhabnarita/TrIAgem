"""
app/exceptions.py — Exceções de negócio centralizadas e handlers FastAPI.

Separa a lógica de erro do código de negócio, permitindo respostas
padronizadas e rastreabilidade.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Exceções de domínio (lançadas nas camadas de serviço/router)
# ---------------------------------------------------------------------------

class TriagemBaseException(Exception):
    """Base de todas as exceções de negócio do TrIAgem."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Erro interno."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class RecursoNaoEncontrado(TriagemBaseException):
    """Recurso inexistente OU pertencente a outra clínica (RN-004: não vaza existência)."""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Recurso não encontrado."


class ConflitoDeNegocio(TriagemBaseException):
    """Violação de regra de negócio (ex: duplicata)."""
    status_code = status.HTTP_409_CONFLICT
    detail = "Conflito de negócio."


class EstadoInvalido(TriagemBaseException):
    """Operação inválida para o estado atual do recurso."""
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Operação inválida para o estado atual."


class TermoNaoAceito(TriagemBaseException):
    """Tutor não aceitou o termo de consentimento antes de submeter a Triagem Pré-Consulta."""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "O tutor precisa aceitar o termo de consentimento antes de enviar a Triagem Pré-Consulta."


class LinkExpirado(TriagemBaseException):
    """Link único da Triagem Pré-Consulta expirado."""
    status_code = status.HTTP_410_GONE
    detail = "Este link da Triagem Pré-Consulta expirou. Solicite um novo link à clínica."


class LimiteExcedido(TriagemBaseException):
    """Rate limit das rotas públicas."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Muitas requisições. Aguarde um instante e tente novamente."


# ---------------------------------------------------------------------------
# Handler global — converte exceções de domínio em respostas JSON
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Registra todos os handlers de exceção na instância FastAPI."""

    @app.exception_handler(TriagemBaseException)
    async def triagem_exception_handler(
        request: Request, exc: TriagemBaseException
    ) -> JSONResponse:
        headers = {"Retry-After": "30"} if isinstance(exc, LimiteExcedido) else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )
