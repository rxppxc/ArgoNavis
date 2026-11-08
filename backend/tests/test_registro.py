"""Logs en archivo (LOG_CARPETA): un archivo por día, limpieza de los viejos y
varios procesos escribiendo a la vez, como los workers de start-backend-prod.bat."""
import logging
import subprocess
import sys
from datetime import date, timedelta

from app.core.registro import ArchivoDiario
from conftest import BACKEND


def _logger(nombre: str, manejador: logging.Handler) -> logging.Logger:
    registro = logging.getLogger(nombre)
    registro.handlers.clear()
    registro.addHandler(manejador)
    registro.setLevel(logging.INFO)
    registro.propagate = False
    return registro


def test_un_archivo_por_dia_y_se_borran_los_viejos(tmp_path, monkeypatch):
    hoy = date.today()
    viejo = tmp_path / f"argonavis-{(hoy - timedelta(days=31)).isoformat()}.log"
    al_limite = tmp_path / f"argonavis-{(hoy - timedelta(days=30)).isoformat()}.log"
    ajeno = tmp_path / "otro-sistema.log"
    for archivo in (viejo, al_limite, ajeno):
        archivo.write_text("antes\n", encoding="utf-8")

    manejador = ArchivoDiario(tmp_path, dias=30)
    manejador.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    registro = _logger("prueba.registro.diario", manejador)
    try:
        registro.info("Aviso enviado: ñandú, tilde y € intactos")
        assert not viejo.exists(), "pasados los días de retención se borra"
        assert al_limite.exists(), "el que tiene justo los días de retención se queda"
        monkeypatch.setattr(manejador, "_hoy", lambda: hoy + timedelta(days=1))
        registro.warning("ya es otro día")
    finally:
        manejador.close()

    assert (tmp_path / f"argonavis-{hoy.isoformat()}.log").read_text(encoding="utf-8") == \
        "INFO Aviso enviado: ñandú, tilde y € intactos\n"
    manana = tmp_path / f"argonavis-{(hoy + timedelta(days=1)).isoformat()}.log"
    assert manana.read_text(encoding="utf-8") == "WARNING ya es otro día\n", "al cambiar el día, archivo nuevo"
    assert not al_limite.exists(), "al día siguiente, el que estaba justo en el límite se borra"
    assert ajeno.exists(), "lo que no es un log de ARGO NAVIS no se toca"


def test_varios_procesos_no_se_pisan_las_lineas(tmp_path):
    """Con el modo "a" de Python, en Windows 4 procesos perdieron 6807 de 12000 líneas."""
    hijo = (
        "import logging, sys\n"
        "from pathlib import Path\n"
        "from app.core.registro import ArchivoDiario\n"
        "manejador = ArchivoDiario(Path(sys.argv[1]), 30)\n"
        "manejador.setFormatter(logging.Formatter('%(message)s'))\n"
        "registro = logging.getLogger('hijo'); registro.addHandler(manejador); registro.setLevel(logging.INFO)\n"
        "for i in range(2000):\n"
        "    registro.info(f'proceso-{sys.argv[2]} linea-{i:05d} ' + 'x' * 100)\n"
    )
    procesos = [subprocess.Popen([sys.executable, "-c", hijo, str(tmp_path), str(p)], cwd=BACKEND)
                for p in range(4)]
    assert all(p.wait(timeout=120) == 0 for p in procesos)

    lineas = (tmp_path / f"argonavis-{date.today().isoformat()}.log").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 8000
    assert all(l.startswith("proceso-") and l.endswith("x" * 100) and len(l) == len(lineas[0]) for l in lineas)
    for p in range(4):
        assert sum(l.startswith(f"proceso-{p} ") for l in lineas) == 2000
