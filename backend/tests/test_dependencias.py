"""Dependencias fijadas (revisión del 2026-11-10).

- requirements.lock trae todas las librerías de Python que se instalan (las
  directas y las que ellas arrastran), con la versión exacta y su hash, y
  coincide con requirements.txt: si alguien edita uno sin regenerar el otro,
  esta prueba falla.
- El Dockerfile instala desde el bloqueo, verificando los hashes.
- Ninguna imagen base usa una etiqueta que cambie sola («nginx:alpine»,
  «python:3.12-slim»): cada build traía lo último sin que nadie lo decidiera.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from ayudas import programa

BACKEND = Path(__file__).resolve().parent.parent
RAIZ = BACKEND.parent
CI = RAIZ / ".github" / "workflows" / "ci.yml"


def _bloqueo() -> dict[str, tuple[str, list[str]]]:
    """{nombre: (versión, hashes)} de requirements.lock."""
    paquetes: dict[str, tuple[str, list[str]]] = {}
    actual = None
    for linea in (BACKEND / "requirements.lock").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", linea)
        if m:
            actual = canonicalize_name(m.group(1))
            paquetes[actual] = (m.group(2), [])
            continue
        h = re.search(r"--hash=sha256:([0-9a-f]{64})", linea)
        if h and actual:
            paquetes[actual][1].append(h.group(1))
    return paquetes


def _directas() -> list[Requirement]:
    lineas = (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [Requirement(linea.split("#")[0].strip()) for linea in lineas if linea.split("#")[0].strip()]


def test_el_bloqueo_coincide_con_requirements():
    bloqueo = _bloqueo()
    assert len(bloqueo) > len(_directas()), "el bloqueo trae también las indirectas"
    for req in _directas():
        nombre = canonicalize_name(req.name)
        assert nombre in bloqueo, f"{req.name} no está en requirements.lock: regenéralo (comando en requirements.txt)"
        version = bloqueo[nombre][0]
        assert req.specifier.contains(version, prereleases=True), \
            f"{req.name}: requirements.txt pide {req.specifier} y el bloqueo tiene {version}: regenéralo"


def test_cada_paquete_del_bloqueo_tiene_su_hash():
    sin_hash = [nombre for nombre, (_, hashes) in _bloqueo().items() if not hashes]
    assert not sin_hash, f"sin hash en requirements.lock: {sin_hash}"


def test_docker_instala_desde_el_bloqueo_con_hashes():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"pip install [^\n]*--require-hashes[^\n]*-r requirements\.lock", dockerfile)
    assert "-r requirements.txt" not in dockerfile


def _imagenes() -> list[tuple[str, str]]:
    """(archivo, imagen) de los Dockerfile, del compose y de la integración continua."""
    encontradas = []
    for ruta in (BACKEND / "Dockerfile", RAIZ / "frontend" / "Dockerfile"):
        texto = ruta.read_text(encoding="utf-8")
        argumentos = dict(re.findall(r"^ARG (\w+)=(\S+)", texto, re.M))
        for imagen in re.findall(r"^FROM (\S+)", texto, re.M):
            m = re.fullmatch(r"\$\{(\w+)\}", imagen)
            encontradas.append((ruta.name, argumentos[m.group(1)] if m else imagen))
    for imagen in re.findall(r"^\s+image:\s*(\S+)", (RAIZ / "docker-compose-prod.yml").read_text(encoding="utf-8"), re.M):
        encontradas.append(("docker-compose-prod.yml", re.sub(r"^\$\{\w+:-(.+)\}$", r"\1", imagen)))   # la de por defecto
    for imagen in re.findall(r"^# POSTGRES_IMAGEN=(\S+)", (RAIZ / ".env.example").read_text(encoding="utf-8"), re.M):
        encontradas.append((".env.example", imagen))
    for imagenes in _postgres_de_la_ci().values():
        encontradas += [("ci.yml", imagen) for imagen in imagenes]
    return encontradas


def _postgres_de_la_ci() -> dict[str, set[str]]:
    """{trabajo: imágenes de PostgreSQL con las que corre}, con las de su matriz."""
    trabajos = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]
    encontradas = {}
    for nombre, trabajo in trabajos.items():
        imagen = trabajo.get("services", {}).get("postgres", {}).get("image")
        if imagen:
            variantes = trabajo.get("strategy", {}).get("matrix", {}).get("postgres", [""])
            encontradas[nombre] = {imagen.replace("${{ matrix.postgres }}", v) for v in variantes}
    return encontradas


@pytest.mark.skipif(programa("bash") is None, reason="sin bash")
@pytest.mark.parametrize("otra", ["", "postgres:18.7-alpine3.24"])
def test_el_paquete_sin_internet_lleva_el_postgresql_que_se_va_a_usar(otra):
    [linea] = re.findall(r"^postgres=.*$", (RAIZ / "empaquetar-sin-internet.sh").read_text(encoding="utf-8"), re.M)
    r = subprocess.run([programa("bash"), "-c", f'{linea}; echo "$postgres"'], cwd=RAIZ, capture_output=True, text=True,
                       env={**os.environ, "POSTGRES_IMAGEN": otra})
    [produccion] = [i for archivo, i in _imagenes() if archivo == "docker-compose-prod.yml" and i.startswith("postgres:")]
    assert r.stdout.strip() == (otra or produccion)


# Las acciones de la CI, en la primera versión mayor que corre con Node 24 (2026-11-22). Con las
# de Node 20, GitHub las forzaba a correr con la 24 y avisaba en cada corrida.
_ACCIONES_CON_NODE_24 = {"actions/checkout": 5, "actions/setup-python": 6, "actions/setup-node": 5,
                         "actions/upload-artifact": 6}


def test_las_acciones_de_la_ci_corren_con_node_24():
    usadas = re.findall(r"uses:\s*([\w-]+/[\w-]+)@v(\d+)\s", CI.read_text(encoding="utf-8"))
    assert len(usadas) == CI.read_text(encoding="utf-8").count("uses:"), "cada acción con su versión mayor (@vN)"
    for accion, mayor in usadas:
        assert accion in _ACCIONES_CON_NODE_24, f"{accion}: ¿desde qué versión corre con Node 24? Agrégala aquí"
        assert int(mayor) >= _ACCIONES_CON_NODE_24[accion], f"{accion}@v{mayor} todavía es de Node 20"


def test_la_ci_revisa_los_tipos_y_la_cobertura():
    """mypy (backend/mypy.ini) sobre la aplicación, y la cobertura de las pruebas con un piso
    (backend/.coveragerc): si baja, la CI falla (2026-11-22)."""
    import configparser

    pasos = "\n".join(p.get("run", "") for p in yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["backend"]["steps"])
    assert "venv/bin/python -m mypy app" in pasos
    assert re.search(r"venv/bin/python -m pytest -q --cov=app\b", pasos)
    tipos = configparser.ConfigParser()
    tipos.read(BACKEND / "mypy.ini", encoding="utf-8")
    assert tipos["mypy"]["plugins"] == "pydantic.mypy" and tipos["mypy"]["check_untyped_defs"] == "True"
    cobertura = configparser.ConfigParser()
    cobertura.read(BACKEND / ".coveragerc", encoding="utf-8")
    assert cobertura["run"]["source"] == "app" and int(cobertura["report"]["fail_under"]) >= 70
    desarrollo = (BACKEND / "requirements-dev.txt").read_text(encoding="utf-8")
    for paquete in ("mypy", "pytest-cov", "coverage"):
        assert re.search(rf"^{paquete}==\d", desarrollo, re.M), f"{paquete} con su versión exacta"


def test_las_imagenes_base_tienen_version_exacta():
    for archivo, imagen in _imagenes():
        if imagen.startswith("argonavis-"):
            continue   # las que construye el propio proyecto
        etiqueta = imagen.split(":", 1)[1] if ":" in imagen else "latest"
        # Al menos mayor.menor (15.20, 1.31.8, 3.12.16…): «alpine», «15» o «3.12-slim» cambian solas.
        assert re.match(r"^\d+\.\d+", etiqueta) and not re.fullmatch(r"\d+\.\d+-slim", etiqueta), \
            f"{archivo}: {imagen} no tiene una versión exacta"
    [produccion] = [i for archivo, i in _imagenes() if archivo == "docker-compose-prod.yml" and i.startswith("postgres:")]
    for trabajo, imagenes in _postgres_de_la_ci().items():
        assert produccion in imagenes, f"el trabajo {trabajo} no prueba con el PostgreSQL de producción ({produccion})"
    # El backend, además, con el del servidor nuevo: la 15 se queda sin soporte en noviembre de 2027.
    assert any(i.startswith("postgres:18.") for i in _postgres_de_la_ci()["backend"])
    # El nginx -t de la integración continua, con el nginx de producción.
    ci = CI.read_text(encoding="utf-8")
    nginx = {imagen for _, imagen in _imagenes() if imagen.startswith("nginx:")} | set(re.findall(r"\bnginx:\d\S*", ci))
    assert len(nginx) == 1, f"la integración continua prueba nginx.conf con otro nginx: {nginx}"
