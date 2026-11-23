"""El respaldo (backup.sh) y la prueba de que se puede restaurar (probar-restauracion.sh).

Los guiones corren de verdad, con un «docker» de mentira en el PATH: no se toca ningún
contenedor. Con PostgreSQL real los corre la integración continua (trabajo contenedores)."""
import gzip
import os
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path

import pytest

from ayudas import programa

RAIZ = Path(__file__).resolve().parents[2]
BASH = programa("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="sin bash")

DOCKER = r"""#!/usr/bin/env bash
echo "$*" >> "$REGISTRO"
case "$*" in
  *"volume inspect"*)      echo "$VOLUMEN" ;;
  *pg_dump*)               echo "SELECT 1;"; exit "${SALIDA_PG_DUMP:-0}" ;;
  *createdb*|*dropdb*)     ;;
  *"FROM documentos_emitidos"*)   [ -s "$EMITIDOS_EN_LA_BASE" ] && cat "$EMITIDOS_EN_LA_BASE" || exit 1 ;;
  *"FROM solicitud_documentos"*)  cat "$DOCUMENTOS_EN_LA_BASE" ;;
  *"FROM alembic_version"*)       echo "${CUENTAS:-b5e1c8d4f207|24|9|40|7}" ;;
  *psql*)                  cat > "$RESTAURADO"; exit "${SALIDA_PSQL:-0}" ;;
esac
"""


class Equipo:
    """Un servidor con su volumen de documentos y su carpeta de respaldos."""

    def __init__(self, carpeta: Path):
        self.volumen, self.respaldos = carpeta / "volumen", carpeta / "respaldos"
        self.registro, self.en_la_base = carpeta / "ordenes.txt", carpeta / "documentos.txt"
        self.emitidos = carpeta / "emitidos.txt"   # vacío: un respaldo de antes, sin esa tabla
        self.restaurado = carpeta / "restaurado.sql"
        programas = carpeta / "programas"
        for c in (self.volumen, self.respaldos, programas):
            c.mkdir()
        self.registro.touch()
        self.en_la_base.touch()
        self.emitidos.touch()
        docker = programas / "docker"
        docker.write_text(DOCKER, encoding="utf-8", newline="\n")
        docker.chmod(0o755)
        self.entorno = {
            **os.environ, "PATH": f"{programas}{os.pathsep}{os.environ['PATH']}",
            "REGISTRO": str(self.registro), "VOLUMEN": self.volumen.as_posix(), "RESTAURADO": str(self.restaurado),
            "DOCUMENTOS_EN_LA_BASE": str(self.en_la_base), "EMITIDOS_EN_LA_BASE": str(self.emitidos),
            "DIR_BACKUPS": self.respaldos.as_posix(),
        }

    def documento(self, ruta: str, contenido: bytes) -> None:
        archivo = self.volumen / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)

    def correr(self, guion: str, **extra) -> subprocess.CompletedProcess:
        return subprocess.run([BASH, guion], cwd=RAIZ, env={**self.entorno, **extra}, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=120)

    def respaldar(self, **extra) -> subprocess.CompletedProcess:
        return self.correr("backup.sh", **extra)

    def copias(self) -> list[Path]:
        return sorted((self.respaldos / "documentos").glob("20*"))

    def bases(self) -> list[Path]:
        return sorted(self.respaldos.glob("argonavis_bd_*.sql.gz"))

    def ordenes(self) -> list[str]:
        return self.registro.read_text(encoding="utf-8").splitlines()


@pytest.fixture
def equipo(tmp_path):
    return Equipo(tmp_path)


def _archivos(carpeta: Path) -> dict[str, bytes]:
    return {a.relative_to(carpeta).as_posix(): a.read_bytes() for a in carpeta.rglob("*") if a.is_file()}


# ── El respaldo ───────────────────────────────────────────────────────────────

def test_respalda_la_base_y_los_documentos(equipo):
    equipo.documento("solicitud-1/a.pdf", b"uno")
    equipo.documento("solicitud-2/b.docx", b"dos")
    r = equipo.respaldar()
    assert r.returncode == 0, r.stdout + r.stderr
    [base], [copia] = equipo.bases(), equipo.copias()
    assert gzip.decompress(base.read_bytes()).strip() == b"SELECT 1;"
    assert _archivos(copia) == {"solicitud-1/a.pdf": b"uno", "solicitud-2/b.docx": b"dos"}
    assert base.name == f"argonavis_bd_{copia.name}.sql.gz", "los dos llevan la misma fecha: se restauran juntos"


def test_la_segunda_noche_solo_agrega_lo_nuevo(equipo):
    equipo.documento("solicitud-1/a.pdf", b"uno")
    assert equipo.respaldar().returncode == 0
    time.sleep(1.1)   # cada copia lleva la hora en el nombre
    equipo.documento("solicitud-2/b.pdf", b"dos")
    assert equipo.respaldar().returncode == 0

    primera, segunda = equipo.copias()
    assert _archivos(segunda) == {"solicitud-1/a.pdf": b"uno", "solicitud-2/b.pdf": b"dos"}
    assert _archivos(primera) == {"solicitud-1/a.pdf": b"uno"}, "la copia anterior no se toca"
    repetido = [c / "solicitud-1" / "a.pdf" for c in (primera, segunda)]
    assert repetido[0].stat().st_ino == repetido[1].stat().st_ino, "lo que ya estaba no ocupa espacio otra vez"


def test_lo_que_se_pierde_en_el_servidor_sigue_en_las_copias(equipo):
    """El sistema ya no borra documentos (2026-11-22): si uno falta o se daña, es una pérdida, y
    la copia no la imita. Lo temporal de un envío en curso no se guarda."""
    equipo.documento("solicitud-1/a.pdf", b"original")
    equipo.documento("solicitud-1/b.pdf", b"se pierde")
    assert equipo.respaldar().returncode == 0
    time.sleep(1.1)
    (equipo.volumen / "solicitud-1" / "b.pdf").unlink()
    equipo.documento("solicitud-1/a.pdf", b"cambiado")
    equipo.documento("solicitud-2/c.pdf", b"nuevo")
    equipo.documento("tmp-0a1b/envio.pdf", b"a medias")
    equipo.documento("solicitud-3/autorizacion-aprobada-1.parcial", b"a medias")
    r = equipo.respaldar()
    assert r.returncode == 0, r.stdout + r.stderr
    primera, segunda = equipo.copias()
    assert _archivos(segunda) == {"solicitud-1/a.pdf": b"original", "solicitud-1/b.pdf": b"se pierde", "solicitud-2/c.pdf": b"nuevo"}
    assert "1 archivo(s) ya no están en el servidor y 1 cambiaron" in r.stdout, "queda dicho en el registro"
    assert _archivos(primera) == {"solicitud-1/a.pdf": b"original", "solicitud-1/b.pdf": b"se pierde"}


def test_si_la_base_no_se_puede_respaldar_no_queda_uno_a_medias(equipo):
    r = equipo.respaldar(SALIDA_PG_DUMP="1")
    assert r.returncode != 0
    assert equipo.bases() == [] and not list(equipo.respaldos.glob("*.parcial"))


def _noches(equipo, *fechas: str) -> None:
    """Respaldos de otras noches: la base y la copia llevan la misma fecha."""
    for fecha in fechas:
        (equipo.respaldos / "documentos" / f"{fecha}_020000").mkdir(parents=True)
        (equipo.respaldos / f"argonavis_bd_{fecha}_020000.sql.gz").write_bytes(b"x")


def _quedan(equipo) -> list[str]:
    copias = [c.name[:10] for c in equipo.copias()]
    assert copias == [b.name[len("argonavis_bd_"):][:10] for b in equipo.bases()], "la base y la copia, de las mismas noches"
    return copias[:-1]   # sin la de hoy


def test_guarda_las_ultimas_noches(equipo):
    _noches(equipo, *(f"2026-11-0{d}" for d in range(1, 6)))
    assert equipo.respaldar(RETENER_DIAS="3", RETENER_MESES="0", RETENER_ANIOS="0").returncode == 0
    assert _quedan(equipo) == ["2026-11-04", "2026-11-05"]


def test_guarda_tambien_una_por_mes_y_una_por_anio(equipo):
    """El margen (2026-11-22): todavía no se sabe cuántos años se conservan. De cada mes y de
    cada año queda la primera noche."""
    _noches(equipo, "2024-03-05", "2024-03-06", "2024-09-01", "2025-01-02", "2025-06-01", "2026-01-03", "2026-01-04",
            "2026-08-01", "2026-09-01", "2026-09-20", "2026-10-02", "2026-10-30", "2026-10-31")
    assert equipo.respaldar(RETENER_DIAS="2", RETENER_MESES="3", RETENER_ANIOS="10").returncode == 0
    # Las 2 últimas noches (la de hoy y la del 31), la primera de los 3 últimos meses (el de hoy,
    # octubre y septiembre) y la primera de cada año.
    assert _quedan(equipo) == ["2024-03-05", "2025-01-02", "2026-01-03", "2026-09-01", "2026-10-02", "2026-10-31"]
    # Otra noche más no cambia las que son de un mes o de un año.
    time.sleep(1.1)
    assert equipo.respaldar(RETENER_DIAS="2", RETENER_MESES="3", RETENER_ANIOS="10").returncode == 0
    assert [f for f in _quedan(equipo) if not f.startswith(time.strftime("%Y-%m"))] == [
        "2024-03-05", "2025-01-02", "2026-01-03", "2026-09-01", "2026-10-02"]


def test_por_defecto_guarda_un_anio_de_meses_y_diez_anios(equipo):
    este = date.today()
    viejos = [f"{a}-01-01" for a in range(este.year - 12, este.year - 1)]
    meses = [f"{a}-{m:02d}-01" for a in (este.year - 1, este.year) for m in range(1, 13) if (a, m) < (este.year, este.month)]
    _noches(equipo, *viejos, *meses)
    assert equipo.respaldar(RETENER_DIAS="1").returncode == 0
    quedan = _quedan(equipo)
    de_un_anio = [f for f in quedan if f.endswith("-01-01")]
    assert {f"{a}-01-01" for a in range(este.year - 9, este.year)} <= set(de_un_anio), "con este, los 10 últimos años"
    assert f"{este.year - 10}-01-01" not in quedan
    assert [f for f in quedan if f in meses][-11:] == meses[-11:], "con este mes, los 12 últimos"
    assert len(quedan) <= 11 + 9


def test_los_tar_de_antes_se_borran_solos(equipo):
    """Hasta el 2026-11-10 los documentos iban en un .tar.gz por noche."""
    viejo = equipo.respaldos / "argonavis_documentos_2026-10-01_020000.tar.gz"
    viejo.write_bytes(b"x")
    hace_un_mes = time.time() - 30 * 86400
    os.utime(viejo, (hace_un_mes, hace_un_mes))
    assert equipo.respaldar().returncode == 0
    assert not viejo.exists()


# ── La prueba de restauración ─────────────────────────────────────────────────

@pytest.fixture
def respaldado(equipo):
    """Con un respaldo de dos documentos, que la base nombra."""
    equipo.documento("solicitud-1/a.pdf", b"uno")
    equipo.documento("solicitud-2/b.docx", b"cuatro")
    equipo.en_la_base.write_text("solicitud-1/a.pdf|3\nsolicitud-2/b.docx|6\n", encoding="utf-8", newline="\n")
    assert equipo.respaldar().returncode == 0
    equipo.registro.write_text("", encoding="utf-8")
    return equipo


def _borra_la_base_de_prueba(equipo) -> bool:
    ordenes = equipo.ordenes()
    return any("createdb" in o for o in ordenes) and "dropdb" in ordenes[-1]


def test_el_ultimo_respaldo_se_restaura(respaldado):
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Resultado: el respaldo se restaura." in r.stdout
    assert "2 de 2 documentos" in r.stdout and "9 solicitudes" in r.stdout
    assert respaldado.restaurado.read_text(encoding="utf-8").strip() == "SELECT 1;"
    assert _borra_la_base_de_prueba(respaldado)
    assert all("argonavis_prueba_restauracion" in o for o in respaldado.ordenes() if "psql" in o or "db " in o), \
        "nunca toca la base de verdad"


def test_tambien_las_autorizaciones_emitidas(respaldado):
    """Las emitidas están en la misma carpeta; un respaldo de antes no tiene esa tabla (los demás casos)."""
    respaldado.emitidos.write_text("solicitud-1/autorizacion-aprobada-1.pdf|4\n", encoding="utf-8", newline="\n")
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 1 and "solicitud-1/autorizacion-aprobada-1.pdf" in r.stdout and "2 de 3" in r.stdout
    (respaldado.copias()[0] / "solicitud-1" / "autorizacion-aprobada-1.pdf").write_bytes(b"%PDF")
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 0 and "3 de 3 documentos" in r.stdout


@pytest.mark.parametrize(("romper", "dice"), [
    (lambda copia: (copia / "solicitud-1" / "a.pdf").unlink(), "solicitud-1/a.pdf"),
    (lambda copia: (copia / "solicitud-2" / "b.docx").write_bytes(b"otra cosa"), "solicitud-2/b.docx"),
], ids=["falta uno", "otro tamaño"])
def test_si_un_documento_no_esta_bien_lo_dice(respaldado, romper, dice):
    romper(respaldado.copias()[0])
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 1 and "NO" in r.stdout and dice in r.stdout and "1 de 2 documentos" in r.stdout
    assert _borra_la_base_de_prueba(respaldado)


def test_un_respaldo_danado_se_detecta_sin_tocar_la_base(respaldado):
    respaldado.bases()[0].write_bytes(b"\x1f\x8bno es un gzip")
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 1 and "dañado" in r.stdout
    assert not any("createdb" in o for o in respaldado.ordenes())


def test_si_la_base_no_carga_lo_dice_y_limpia(respaldado):
    r = respaldado.correr("probar-restauracion.sh", SALIDA_PSQL="3")
    assert r.returncode == 1 and "NO se pudo restaurar" in r.stdout
    assert _borra_la_base_de_prueba(respaldado)


def test_una_base_vacia_no_pasa_por_buena(respaldado):
    r = respaldado.correr("probar-restauracion.sh", CUENTAS="b5e1c8d4f207|24|0|0|0")
    assert r.returncode == 1 and "ningún usuario" in r.stdout


def test_sin_respaldos_o_sin_la_copia_de_esa_noche(equipo, respaldado):
    shutil.rmtree(respaldado.copias()[0])
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 1 and "documentos de esa noche" in r.stdout
    respaldado.bases()[0].unlink()
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 1 and "No hay respaldos" in r.stdout


def test_prueba_el_mas_reciente(respaldado):
    time.sleep(1.1)
    respaldado.documento("solicitud-3/c.pdf", b"nuevo")
    with respaldado.en_la_base.open("a", encoding="utf-8", newline="\n") as f:
        f.write("solicitud-3/c.pdf|5\n")
    assert respaldado.respaldar().returncode == 0
    r = respaldado.correr("probar-restauracion.sh")
    assert r.returncode == 0 and "3 de 3 documentos" in r.stdout and respaldado.bases()[-1].name in r.stdout
