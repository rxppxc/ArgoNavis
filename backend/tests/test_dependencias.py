"""Dependencias fijadas (revisión del 2026-11-10).

- requirements.lock trae todas las librerías de Python que se instalan (las
  directas y las que ellas arrastran), con la versión exacta y su hash, y
  coincide con requirements.txt: si alguien edita uno sin regenerar el otro,
  esta prueba falla.
- El Dockerfile instala desde el bloqueo, verificando los hashes.
- Ninguna imagen base usa una etiqueta que cambie sola («nginx:alpine»,
  «python:3.12-slim»): cada build traía lo último sin que nadie lo decidiera.
"""
import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BACKEND = Path(__file__).resolve().parent.parent
RAIZ = BACKEND.parent


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
    for ruta in (RAIZ / "docker-compose-prod.yml", RAIZ / ".github" / "workflows" / "ci.yml"):
        for imagen in re.findall(r"^\s+image:\s*(\S+)", ruta.read_text(encoding="utf-8"), re.M):
            encontradas.append((ruta.name, imagen))
    return encontradas


def test_las_imagenes_base_tienen_version_exacta():
    for archivo, imagen in _imagenes():
        if imagen.startswith("argonavis-"):
            continue   # las que construye el propio proyecto
        etiqueta = imagen.split(":", 1)[1] if ":" in imagen else "latest"
        # Al menos mayor.menor (15.19, 1.31.8, 3.12.16…): «alpine», «15» o «3.12-slim» cambian solas.
        assert re.match(r"^\d+\.\d+", etiqueta) and not re.fullmatch(r"\d+\.\d+-slim", etiqueta), \
            f"{archivo}: {imagen} no tiene una versión exacta"
    postgres = {imagen for _, imagen in _imagenes() if imagen.startswith("postgres:")}
    assert len(postgres) == 1, f"la integración continua y producción usan otro PostgreSQL: {postgres}"
    # El nginx -t de la integración continua, con el nginx de producción.
    ci = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    nginx = {imagen for _, imagen in _imagenes() if imagen.startswith("nginx:")} | set(re.findall(r"\bnginx:\d\S*", ci))
    assert len(nginx) == 1, f"la integración continua prueba nginx.conf con otro nginx: {nginx}"
