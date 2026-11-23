"""Las órdenes de consola (python -m app.…) corren solas en el servidor, sin el resto de la
aplicación (2026-11-22).

Dentro de pytest ya está cargada toda la aplicación, así que una prueba que las llama desde
aquí no ve lo que les falta al correr solas. Por eso aquí corren en un proceso aparte, como
en el servidor. La integración continua encontró así que asignar_rol --crear-local (el
primer SysAdmin de una instalación nueva) se caía: «expression 'AgenciaNaviera' failed to
locate a name»."""
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ORDENES = sorted(
    ".".join(archivo.relative_to(BACKEND).with_suffix("").parts)
    for archivo in (BACKEND / "app").rglob("*.py")
    if 'if __name__ == "__main__"' in archivo.read_text(encoding="utf-8")
)


def _correr(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argumentos], cwd=BACKEND, env=os.environ.copy(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_estan_todas():
    assert {"app.infrastructure.asignar_rol", "app.infrastructure.permisos_bd",
            "app.infrastructure.revisar_documentos"} <= set(ORDENES)


@pytest.mark.parametrize("orden", ORDENES)
def test_cada_orden_tiene_todos_los_modelos(orden):
    """Las relaciones se nombran por texto («AgenciaNaviera») y SQLAlchemy las resuelve en la
    primera consulta: todas las tablas tienen que estar cargadas."""
    r = _correr("-c", f"import {orden}; from sqlalchemy.orm import configure_mappers; configure_mappers()")
    assert r.returncode == 0, r.stderr[-1500:]


def test_el_primer_sysadmin_se_crea_desde_la_consola():
    """Como en una instalación nueva (README → Primer SysAdmin), y como lo hace la CI."""
    nombre = f"consola.{secrets.token_hex(3)}"
    r = _correr("-m", "app.infrastructure.asignar_rol", nombre, "SysAdmin", "--crear-local")
    assert r.returncode == 0, r.stderr[-1500:]
    assert re.search(r"se cambia al entrar\): \S{12,}$", r.stdout, re.M), r.stdout
    assert f"{nombre} ahora tiene el rol SysAdmin." in r.stdout
