"""Salida de los logs de la aplicación (el logger "app" y todos sus hijos).

uvicorn solo configura sus propios loggers: sin esto, Python descartaba los
logger.info de la app (correos enviados, solicitudes expiradas) y mostraba los
warning y error sin fecha. Se configura "app" y no la raíz para no duplicar el
eco de SQL de desarrollo, que SQLAlchemy imprime con su propio handler.
"""
import logging

_FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configurar_registro(nivel: int = logging.INFO) -> None:
    registro = logging.getLogger("app")
    if registro.handlers:   # ya configurado (p. ej. al recargar en desarrollo)
        return
    salida = logging.StreamHandler()
    salida.setFormatter(logging.Formatter(_FORMATO))
    registro.addHandler(salida)
    registro.setLevel(nivel)
