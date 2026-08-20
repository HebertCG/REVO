"""
client_ip.py — Determina la IP real del cliente sin confiar de mas.

X-Forwarded-For lo puede escribir cualquiera. Solo es fiable la parte que
anadieron proxies que controlamos nosotros, y eso son los ULTIMOS saltos de
la cadena, no los primeros. Contar bien los saltos de confianza es
obligatorio: con la cuenta mal puesta, el limite por IP se salta con una
cabecera.
"""
from __future__ import annotations

import ipaddress

FORWARDED_HEADER = "x-forwarded-for"

# Una cabecera legitima con varios saltos rara vez pasa de unos cientos de
# bytes. Un valor enorme solo aparece cuando alguien intenta inflar las
# llaves de Redis o el log.
MAX_HEADER_LENGTH = 512

UNKNOWN_IP = "unknown"


def _is_valid_ip(candidate: str) -> bool:
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        return False


def _socket_ip(request) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host or UNKNOWN_IP


def extract_client_ip(request, trusted_proxy_count: int = 0) -> str:
    """
    Args:
        request: peticion con `.client.host` y `.headers` (Starlette/FastAPI).
        trusted_proxy_count: cuantos proxies propios hay delante de la app.
            0 = la app recibe trafico directo, la cabecera se ignora entera.
            1 = solo Nginx delante.
            2 = Cloudflare y luego Nginx.

    Returns:
        La IP del cliente, o "unknown" si no se puede determinar.
    """
    socket_ip = _socket_ip(request)

    if trusted_proxy_count <= 0:
        return socket_ip

    raw = (request.headers.get(FORWARDED_HEADER) or "").strip()
    if not raw or len(raw) > MAX_HEADER_LENGTH:
        return socket_ip

    saltos = [parte.strip() for parte in raw.split(",") if parte.strip()]
    if not saltos:
        return socket_ip

    # El ultimo elemento lo escribio el proxy mas cercano a la app. Se
    # retrocede tantas posiciones como proxies propios haya; lo que quede a
    # la izquierda de ahi lo pudo escribir el cliente y no vale nada.
    indice = max(0, len(saltos) - trusted_proxy_count)
    candidato = saltos[indice]

    return candidato if _is_valid_ip(candidato) else socket_ip
