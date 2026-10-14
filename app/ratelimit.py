"""
app/ratelimit.py — Rate limit simples em memória (janela deslizante por IP).

Protege rotas públicas (link do tutor) e o login contra abuso/força bruta.
Em produção com múltiplas instâncias, trocar o armazenamento por Redis
(a interface `limitar` permanece a mesma).
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.exceptions import LimiteExcedido

_JANELAS: dict[str, deque[float]] = defaultdict(deque)


def _ip(request: Request) -> str:
    # Atrás de proxy/load balancer confiável, use X-Forwarded-For.
    return request.client.host if request.client else "desconhecido"


def limitar(nome: str, maximo: int, janela_segundos: int = 60):
    """Fábrica de dependência: no máximo `maximo` requisições por IP a cada janela."""

    async def _dep(request: Request) -> None:
        agora = time.monotonic()
        chave = f"{nome}:{_ip(request)}"
        fila = _JANELAS[chave]
        while fila and agora - fila[0] > janela_segundos:
            fila.popleft()
        if len(fila) >= maximo:
            raise LimiteExcedido()
        fila.append(agora)

    return _dep


def resetar_limites() -> None:
    """Uso em testes."""
    _JANELAS.clear()

