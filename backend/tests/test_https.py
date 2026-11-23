"""HTTPS listo para activar (2026-11-22): solo falta el certificado, que lo da la DTI.

Sin él, ARGO NAVIS atiende por HTTP, como siempre. Con el certificado en certificados/https y
USAR_HTTPS=true en el .env, nginx atiende por HTTPS y el 80 solo redirige.

El guion que lo decide al arrancar (frontend/nginx/elegir-modo.sh) corre aquí de verdad. Que la
pila entera atienda así lo prueba la integración continua (trabajo «contenedores»), con un
certificado de prueba."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.core.config import Configuracion
from ayudas import programa

RAIZ = Path(__file__).resolve().parents[2]
FRONTEND = RAIZ / "frontend"
NGINX = (FRONTEND / "nginx.conf").read_text(encoding="utf-8")
SERVICIOS = yaml.safe_load((RAIZ / "docker-compose-prod.yml").read_text(encoding="utf-8"))["services"]

SH = programa("sh")
con_sh = pytest.mark.skipif(SH is None, reason="sin sh")


def _conf(nombre: str) -> str:
    """Un archivo de frontend/nginx, sin comentarios."""
    texto = (FRONTEND / "nginx" / nombre).read_text(encoding="utf-8")
    return re.sub(r"\s*#.*", "", texto).strip()


class Contenedor:
    """El contenedor de nginx al arrancar: sus certificados y lo que el guion le deja a nginx."""

    def __init__(self, carpeta: Path):
        self.certificados, self.salida = carpeta / "certificados", carpeta / "run" / "argonavis"
        self.certificados.mkdir()

    def con_certificado(self) -> "Contenedor":
        for archivo in ("argonavis.crt", "argonavis.key"):
            (self.certificados / archivo).write_text("contenido", encoding="utf-8")
        return self

    def arrancar(self, **entorno: str) -> subprocess.CompletedProcess:
        limpio = {k: v for k, v in os.environ.items() if k not in ("USAR_HTTPS", "APP_URL")}
        carpetas = (FRONTEND / "nginx", self.certificados, self.salida)
        return subprocess.run(
            [SH, (FRONTEND / "nginx" / "elegir-modo.sh").as_posix(), *(c.as_posix() for c in carpetas)],
            env={**limpio, **entorno}, capture_output=True, encoding="utf-8", errors="replace", timeout=60,
        )

    def escucha(self) -> str:
        return re.sub(r"\s*#.*", "", (self.salida / "escucha.conf").read_text(encoding="utf-8")).strip()

    def redireccion(self) -> str:
        return (self.salida / "redireccion.conf").read_text(encoding="utf-8")


@pytest.fixture
def contenedor(tmp_path):
    return Contenedor(tmp_path)


# ── HTTP o HTTPS, al arrancar ─────────────────────────────────────────────────

@con_sh
@pytest.mark.parametrize("entorno", [{}, {"USAR_HTTPS": ""}, {"USAR_HTTPS": "false"}, {"USAR_HTTPS": "FALSE"}],
                         ids=["sin la variable", "vacía", "false", "FALSE"])
def test_sin_https_atiende_por_http_como_siempre(contenedor, entorno):
    """Aunque el certificado ya esté puesto: se activa a propósito, con USAR_HTTPS."""
    r = contenedor.con_certificado().arrancar(APP_URL="http://192.168.1.10", **entorno)
    assert r.returncode == 0, r.stderr
    assert contenedor.escucha() == "listen 8080;"
    assert contenedor.redireccion() == ""


@con_sh
@pytest.mark.parametrize(("app_url", "nombre"), [
    ("https://argonavis.prueba.pa", "argonavis.prueba.pa"),
    ("https://argonavis.prueba.pa/", "argonavis.prueba.pa"),
    ("https://argonavis.prueba.pa:8443/x", "argonavis.prueba.pa:8443"),
])
@pytest.mark.parametrize("valor", ["true", "True"])
def test_con_https_el_80_lleva_al_nombre_del_certificado(contenedor, app_url, nombre, valor):
    """Y no al que escribió el usuario: por la IP, el certificado no coincide y el navegador advierte."""
    r = contenedor.con_certificado().arrancar(USAR_HTTPS=valor, APP_URL=app_url)
    assert r.returncode == 0, r.stderr
    escucha = contenedor.escucha()
    assert escucha.startswith("listen 8443 ssl;") and "listen 8080" not in escucha
    redireccion = re.sub(r"\s*#.*", "", contenedor.redireccion())
    assert re.findall(r"\blisten ([^;]+);", redireccion) == ["8080"]
    assert re.findall(r"\breturn ([^;]+);", redireccion) == [f"301 https://{nombre}$request_uri"]


@con_sh
@pytest.mark.parametrize(("falta", "entorno", "dice"), [
    ("argonavis.crt", {}, "certificados/https/argonavis.crt"),
    ("argonavis.key", {}, "certificados/https/argonavis.key"),
    ("", {"APP_URL": "http://argonavis.prueba.pa"}, "APP_URL"),
    ("", {"APP_URL": ""}, "APP_URL"),
    ("", {"APP_URL": "https://"}, "APP_URL"),
    ("", {"APP_URL": "https://a;return 200 x"}, "APP_URL"),
    ("", {"APP_URL": "https://a\nb"}, "APP_URL"),
    ("", {"USAR_HTTPS": "si"}, "USAR_HTTPS=si"),
], ids=["sin certificado", "sin clave", "APP_URL sin https", "sin APP_URL", "APP_URL sin nombre",
        "APP_URL con otra cosa", "APP_URL con un salto", "USAR_HTTPS mal escrito"])
def test_si_algo_falta_no_arranca_y_dice_que(contenedor, falta, entorno, dice):
    """Volver solo a HTTP, sin que nadie se entere, sería peor: las contraseñas irían en claro."""
    contenedor.con_certificado()
    if falta:
        (contenedor.certificados / falta).unlink()
    r = contenedor.arrancar(**{"USAR_HTTPS": "true", "APP_URL": "https://argonavis.prueba.pa", **entorno})
    assert r.returncode != 0 and dice in r.stderr, r.stdout + r.stderr
    assert not list(contenedor.salida.glob("*.conf")), "no deja una configuración a medias"


@con_sh
@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="Windows o root leen todo")
def test_una_clave_que_nginx_no_puede_leer(contenedor):
    """La clave es del usuario 101 (nginx corre sin root): si quedó de otro, dice cómo arreglarlo."""
    (contenedor.con_certificado().certificados / "argonavis.key").chmod(0)
    r = contenedor.arrancar(USAR_HTTPS="true", APP_URL="https://argonavis.prueba.pa")
    assert r.returncode != 0 and "chown 101" in r.stderr


@con_sh
def test_volver_a_http_quita_la_redireccion(contenedor):
    contenedor.con_certificado().arrancar(USAR_HTTPS="true", APP_URL="https://argonavis.prueba.pa")
    assert contenedor.arrancar(USAR_HTTPS="false").returncode == 0
    assert contenedor.escucha() == "listen 8080;" and contenedor.redireccion() == ""


@con_sh
def test_la_clave_no_sale_en_el_registro(contenedor):
    r = contenedor.con_certificado().arrancar(USAR_HTTPS="true", APP_URL="https://argonavis.prueba.pa")
    assert r.returncode == 0 and "contenido" not in r.stdout + r.stderr


# ── La configuración de nginx ─────────────────────────────────────────────────

def test_http_y_https_son_el_mismo_sitio():
    """Un solo server con las cabeceras, los topes y las rutas: solo cambia dónde escucha."""
    servidor = NGINX[NGINX.index("server {"):]
    assert NGINX.count("server {") == 1
    assert re.findall(r"^\s*include (\S+);", servidor, re.M) == ["/run/argonavis/escucha.conf"]
    assert re.findall(r"^include (\S+);", NGINX, re.M) == ["/run/argonavis/redireccion.conf"]
    # Aparte, solo el chequeo de salud del contenedor, que no sale de él.
    assert re.findall(r"^\s*listen (\S+);", NGINX, re.M) == ["127.0.0.1:8081"]


def test_solo_tls_vigente():
    """TLS 1.2 y 1.3, y en 1.2 solo cifrados con secreto hacia adelante y autenticados."""
    https = _conf("https.conf")
    assert re.findall(r"ssl_protocols ([^;]+);", https) == ["TLSv1.2 TLSv1.3"]
    [cifrados] = re.findall(r"ssl_ciphers ([^;]+);", https)
    for cifrado in cifrados.split(":"):
        assert re.fullmatch(r"ECDHE-(ECDSA|RSA)-(AES(128|256)-GCM-SHA(256|384)|CHACHA20-POLY1305)", cifrado), cifrado
    assert re.search(r"ssl_session_tickets off;", https)


def test_hsts_solo_con_https():
    """El navegador que ya entró por HTTPS no vuelve a probar HTTP. Por HTTP no se manda, y
    /assets/ la repite porque nginx no hereda cabeceras donde hay otras propias."""
    m = re.search(r"map \$https \$hsts \{([^}]*)\}", NGINX)
    valores = dict(re.findall(r'(\w+)\s+"([^"]*)";', m.group(1)))
    assert valores["default"] == "" and int(valores["on"].removeprefix("max-age=")) >= 180 * 24 * 3600
    assert len(re.findall(r"add_header Strict-Transport-Security \$hsts always;", NGINX)) == \
        len(re.findall(r"add_header X-Content-Type-Options", NGINX)) == 2


def test_la_redireccion_tambien_queda_en_los_accesos():
    redireccion = _conf("redireccion.conf")
    assert re.search(r"access_log /var/log/argonavis/acceso-\$dia\.log main;", redireccion)
    assert re.search(r"root /usr/share/nginx/html;", redireccion), "con una variable en el nombre, hace falta la raíz"
    assert re.search(r"server_tokens off;", redireccion)


# ── Los certificados en el servidor ───────────────────────────────────────────

def _carpetas_del_servidor(servicio: str) -> dict[str, tuple[str, set[str]]]:
    """{carpeta del servidor: (carpeta del contenedor, opciones)}."""
    partes = (v.split(":") for v in SERVICIOS[servicio].get("volumes", []) if v.startswith("./"))
    return {p[0]: (p[1], set(p[2].split(",")) if len(p) > 2 else set()) for p in partes}


def test_cada_contenedor_ve_solo_lo_suyo_y_sin_poder_cambiarlo():
    """La clave privada, solo nginx; la CA interna (Active Directory y correo), solo el backend."""
    carpetas = {servicio: _carpetas_del_servidor(servicio) for servicio in SERVICIOS}
    assert {s: list(c) for s, c in carpetas.items() if c} == {
        "backend": ["./certificados/ca"], "frontend": ["./certificados/https"]}
    assert carpetas["frontend"]["./certificados/https"][0] == "/certificados"
    assert carpetas["backend"]["./certificados/ca"][0] == "/certificados/ca"
    for montadas in carpetas.values():
        for _, opciones in montadas.values():
            assert "ro" in opciones


def test_https_se_activa_en_el_env_y_por_defecto_no():
    entorno = SERVICIOS["frontend"]["environment"]
    assert entorno["USAR_HTTPS"] == "${USAR_HTTPS:-false}" and entorno["APP_URL"] == "${APP_URL}"
    ejemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^USAR_HTTPS=false$", ejemplo, re.M)
    assert "/certificados/ca/" in ejemplo, "dónde va la CA del Active Directory y del correo"


@pytest.mark.parametrize("archivo", ["certificados/https/argonavis.key", "certificados/https/argonavis.crt",
                                     "certificados/https/clave-vieja", "certificados/ca/snm.pem", "argonavis.key",
                                     "argonavis.pfx", "argonavis.csr"])
def test_los_certificados_no_van_al_repositorio(archivo):
    git = programa("git")
    if git is None:
        pytest.skip("sin git")
    r = subprocess.run([git, "check-ignore", "-q", archivo], cwd=RAIZ)
    assert r.returncode == 0, f"{archivo} se subiría con un commit"


@pytest.mark.parametrize("carpeta", ["https", "ca"])
def test_la_carpeta_si_va(carpeta):
    """Vacía: si no existiera, Docker la crearía como root."""
    git = programa("git")
    if git is None:
        pytest.skip("sin git")
    assert (RAIZ / "certificados" / carpeta / ".gitkeep").exists()
    r = subprocess.run([git, "check-ignore", "-q", f"certificados/{carpeta}/.gitkeep"], cwd=RAIZ)
    assert r.returncode == 1


def test_la_imagen_lleva_el_guion_y_lo_corre_al_arrancar():
    """La imagen de nginx solo corre los guiones de /docker-entrypoint.d que son ejecutables, y
    el permiso no viaja en un commit hecho en Windows: se lo da el Dockerfile."""
    dockerfile = (FRONTEND / "Dockerfile").read_text(encoding="utf-8")
    [destino] = re.findall(r"^COPY nginx/elegir-modo\.sh (/docker-entrypoint\.d/\S+\.sh)$", dockerfile, re.M)
    assert re.search(rf"chmod 755 {re.escape(destino)}", dockerfile)
    assert re.search(r"^COPY nginx/\S*\.conf /etc/nginx/argonavis/$", dockerfile, re.M)
    assert (FRONTEND / "nginx" / "elegir-modo.sh").read_bytes().count(b"\r") == 0
    assert (FRONTEND / "nginx" / "elegir-modo.sh").read_text(encoding="utf-8").startswith("#!/bin/sh\n")


# ── TLS con el Active Directory y con el correo ───────────────────────────────

@pytest.mark.parametrize(("extra", "variable"), [
    ({"LDAP_USAR_SSL": True}, "LDAP_CA_CERT"), ({"LDAP_STARTTLS": True}, "LDAP_CA_CERT"),
    ({"MAIL_USAR_SSL": True}, "MAIL_CA_CERT"), ({"MAIL_STARTTLS": True}, "MAIL_CA_CERT"),
])
def test_una_ca_que_no_esta_se_dice_al_arrancar(tmp_path, extra, variable):
    """Antes: «invalid CA public key file», sin decir cuál, o cada correo fallando."""
    ruta = tmp_path / "snm.pem"
    with pytest.raises(ValidationError) as e:
        Configuracion(**extra, **{variable: str(ruta)})
    assert variable in str(e.value) and "certificados/ca" in str(e.value)
    ruta.write_text("pem", encoding="utf-8")
    assert getattr(Configuracion(**extra, **{variable: str(ruta)}), variable) == str(ruta)


def test_sin_tls_la_ca_no_se_mira(tmp_path):
    assert Configuracion(LDAP_CA_CERT=str(tmp_path / "no-esta.pem"), MAIL_CA_CERT=str(tmp_path / "no-esta.pem"))
