"""Texto sin tildes, para comparar y para nombres de archivo (auditoría del 2026-11-14)."""
import unicodedata


def sin_tildes(texto: str) -> str:
    """"Atlántico" → "Atlantico": sin tildes ni diéresis (la ñ queda como n).

    Con NFD, como `sinTildes` en el frontend: la política de contraseñas, que lo
    usa, está espejada en frontend/src/utils/contrasena.ts."""
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def slug(texto: str) -> str:
    """"Sector Atlántico" → "sector-atlantico": solo letras ASCII, números y guiones.
    Para nombres de archivo, que van en una cabecera HTTP."""
    plano = sin_tildes(texto).encode("ascii", "ignore").decode("ascii").lower()
    return "-".join("".join(c if c.isalnum() else " " for c in plano).split())
