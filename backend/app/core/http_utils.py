"""Utilidades comunes para inspeccionar peticiones HTTP entrantes."""
from fastapi import Request


def obtener_ip(request: Request) -> str | None:
    """IP del cliente. Detrás de un proxy, uvicorn la resuelve con
    --proxy-headers solo si el proxy es de confianza (--forwarded-allow-ips);
    leer X-Forwarded-For aquí directamente permitiría falsearla."""
    return request.client.host if request.client else None


def obtener_agente(request: Request) -> str | None:
    """User-Agent del cliente, truncado a 500 caracteres."""
    ua = request.headers.get("User-Agent", "")
    return ua[:500] if ua else None
