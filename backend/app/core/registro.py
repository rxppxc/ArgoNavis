"""Salida de los logs de la aplicación (el logger "app" y todos sus hijos).

uvicorn solo configura sus propios loggers: sin esto, Python descartaba los
logger.info de la app (correos enviados, solicitudes expiradas) y mostraba los
warning y error sin fecha. Se configura "app" y no la raíz para no duplicar el
eco de SQL de desarrollo, que SQLAlchemy imprime con su propio handler.

Con LOG_CARPETA, además de la consola quedan en un archivo por día
(`argonavis-AAAA-MM-DD.log`), junto con los errores del servidor (`uvicorn.error`,
por ejemplo una excepción no atrapada). No van los accesos de cada petición: los
registra el proxy y las acciones quedan en la bitácora.
"""
import logging
import os
import re
from contextlib import suppress
from datetime import date, timedelta
from pathlib import Path

from app.core.config import obtener_configuracion

_FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_PREFIJO = "argonavis-"
_NOMBRE_DIARIO = re.compile(rf"^{_PREFIJO}(\d{{4}}-\d{{2}}-\d{{2}})\.log$")


def _abrir_para_agregar(ruta: Path):
    """Abre el archivo para agregar al final.

    En Windows, con FILE_APPEND_DATA y sin FILE_WRITE_DATA: el sistema escribe
    cada bloque al final de una sola vez. El modo "a" de Python busca el final y
    escribe en dos pasos, y los 4 workers de start-backend-prod.bat se pisaban:
    en una prueba con 4 procesos se perdieron 6807 de 12000 líneas."""
    if os.name != "nt":
        return open(ruta, "a", encoding="utf-8")   # O_APPEND ya es atómico en Linux
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    FILE_APPEND_DATA, SYNCHRONIZE = 0x0004, 0x00100000
    COMPARTIDO = 0x1 | 0x2 | 0x4    # lectura, escritura y borrado: los demás workers y la limpieza
    OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL = 4, 0x80
    manejador = kernel32.CreateFileW(str(ruta), FILE_APPEND_DATA | SYNCHRONIZE, COMPARTIDO, None,
                                     OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
    if manejador == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return open(msvcrt.open_osfhandle(manejador, os.O_WRONLY | os.O_BINARY), "w", encoding="utf-8")


class ArchivoDiario(logging.Handler):
    """Un archivo por día que nunca se renombra. Rotar renombrando (como
    RotatingFileHandler) falla en Windows mientras otro worker tiene el archivo
    abierto. Al empezar un día nuevo borra los de más de `dias` días."""

    def __init__(self, carpeta: Path, dias: int):
        super().__init__()
        self.carpeta = Path(carpeta)
        self.dias = max(dias, 1)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._fecha: date | None = None
        self._archivo = None

    def _hoy(self) -> date:
        return date.today()   # hora del servidor

    def emit(self, registro: logging.LogRecord) -> None:
        try:
            hoy = self._hoy()
            if hoy != self._fecha:
                self._cambiar_de_dia(hoy)
            self._archivo.write(self.format(registro) + "\n")
            self._archivo.flush()   # una línea, una escritura: entera al final del archivo
        except Exception:
            self.handleError(registro)

    def _cambiar_de_dia(self, hoy: date) -> None:
        if self._archivo:
            self._archivo.close()
        self._archivo = _abrir_para_agregar(self.carpeta / f"{_PREFIJO}{hoy.isoformat()}.log")
        self._fecha = hoy
        limite = hoy - timedelta(days=self.dias)
        for ruta in self.carpeta.iterdir():
            nombre = _NOMBRE_DIARIO.match(ruta.name)
            if nombre and date.fromisoformat(nombre.group(1)) < limite:
                # missing_ok: otro worker pudo borrarlo primero. Si no se puede
                # (permisos), se vuelve a intentar al día siguiente: no es motivo
                # para perder la línea que se está escribiendo.
                with suppress(OSError):
                    ruta.unlink(missing_ok=True)

    def close(self) -> None:
        with self.lock:
            if self._archivo:
                self._archivo.close()
                self._archivo = None
        super().close()


def configurar_registro() -> None:
    configuracion = obtener_configuracion()
    registro = logging.getLogger("app")
    if registro.handlers:   # ya configurado (p. ej. al recargar en desarrollo)
        return
    formato = logging.Formatter(_FORMATO)
    salida = logging.StreamHandler()
    salida.setFormatter(formato)
    registro.addHandler(salida)
    registro.setLevel(configuracion.LOG_NIVEL)
    if configuracion.LOG_CARPETA:
        archivo = ArchivoDiario(Path(configuracion.LOG_CARPETA), configuracion.LOG_DIAS)
        archivo.setFormatter(formato)
        registro.addHandler(archivo)
        logging.getLogger("uvicorn.error").addHandler(archivo)
