"""Contenedores endurecidos (2026-11-22).

Si alguien logra ejecutar algo dentro de un contenedor (un fallo de nginx, de PostgreSQL o
de una librería que lee lo que suben las agencias), que no sea root, que no tenga
privilegios del sistema, que no pueda cambiar lo que hay en la imagen y que desde nginx no
se llegue a la base de datos.

Aquí se revisa lo que dicen docker-compose-prod.yml y los Dockerfile. Que la pila arranque
y funcione así lo prueban la integración continua (trabajo «contenedores») y, en cada
servidor, verificar-despliegue.sh."""
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((RAIZ / "docker-compose-prod.yml").read_text(encoding="utf-8"))
SERVICIOS: dict[str, dict] = COMPOSE["services"]
NGINX = (RAIZ / "frontend" / "nginx.conf").read_text(encoding="utf-8")


def _dockerfile(servicio: str) -> str:
    return (RAIZ / servicio / "Dockerfile").read_text(encoding="utf-8")


def _redes(servicio: str) -> set[str]:
    return set(SERVICIOS[servicio].get("networks") or ["default"])


def _montajes(servicio: str) -> dict[str, str]:
    """{carpeta del contenedor: volumen}."""
    return dict(reversed(v.split(":")[:2]) for v in SERVICIOS[servicio].get("volumes", []))


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_sin_privilegios_y_con_la_imagen_de_solo_lectura(servicio):
    definicion = SERVICIOS[servicio]
    assert definicion.get("cap_drop") == ["ALL"] and "cap_add" not in definicion
    assert definicion.get("security_opt") == ["no-new-privileges:true"]
    assert definicion.get("read_only") is True
    assert not definicion.get("privileged") and "pid" not in definicion and "network_mode" not in definicion


def test_ninguno_corre_como_root():
    assert SERVICIOS["postgres_db"].get("user") == "70:70"   # postgres, en la imagen Alpine
    for servicio, usuario in (("backend", "argonavis"), ("frontend", "nginx")):
        assert re.findall(r"^USER (\S+)", _dockerfile(servicio), re.M)[-1:] == [usuario], servicio
        assert "user" not in SERVICIOS[servicio], "manda el USER del Dockerfile"


def test_nginx_no_alcanza_a_la_base():
    assert _redes("frontend").isdisjoint(_redes("postgres_db"))
    assert _redes("frontend") & _redes("backend") and _redes("postgres_db") & _redes("backend")
    assert set(COMPOSE["networks"]) == {"default", "datos"}


def test_la_red_de_la_base_no_ocupa_un_rango_grande():
    """Docker le daría un /16 de 172.x; si coincide con una red del SNM o de la VPN, el
    servidor deja de alcanzarla. Va uno chico y se puede cambiar en el .env (RED_DATOS)."""
    [configuracion] = COMPOSE["networks"]["datos"]["ipam"]["config"]
    m = re.fullmatch(r"\$\{RED_DATOS:-(\S+)/(\d+)\}", configuracion["subnet"])
    assert m and int(m.group(2)) >= 28, configuracion
    assert "RED_DATOS" in (RAIZ / ".env.example").read_text(encoding="utf-8")


def test_solo_nginx_se_publica_en_la_red():
    assert "ports" not in SERVICIOS["backend"]
    assert all(p.startswith("127.0.0.1:") for p in SERVICIOS["postgres_db"].get("ports", []))


def test_el_puerto_de_nginx_es_el_mismo_en_todas_partes():
    """Sin root no se puede escuchar en el 80: nginx usa otro y Docker lo publica en el 80."""
    [puerto] = re.findall(r"^\s*listen (\d+);", NGINX, re.M)
    assert int(puerto) > 1024
    assert SERVICIOS["frontend"]["ports"] == [f"80:{puerto}"]
    assert re.findall(r"^EXPOSE (\d+)", _dockerfile("frontend"), re.M) == [puerto]
    assert f"http://127.0.0.1:{puerto}/" in SERVICIOS["frontend"]["healthcheck"]["test"]
    # Si nginx redirige, que no agregue su puerto interno a la dirección.
    assert re.search(r"^\s*absolute_redirect off;", NGINX, re.M)


@pytest.mark.parametrize(("servicio", "carpeta"), [("backend", "/tmp"), ("frontend", "/var/cache/nginx")])
def test_lo_que_se_sube_pasa_por_el_disco_y_no_por_la_memoria(servicio, carpeta):
    """Un envío pesa hasta 345 MB y nginx y el backend lo guardan mientras llega. En un
    tmpfs contaría para la memoria del contenedor (256 MB el de nginx) y lo tumbaría."""
    volumen = _montajes(servicio).get(carpeta)
    assert volumen in COMPOSE["volumes"], f"{carpeta} de {servicio} tiene que ser un volumen"
    assert not any(t.split(":")[0] == carpeta for t in SERVICIOS[servicio].get("tmpfs", []))


def test_los_registros_sobreviven_al_despliegue():
    """Docker borra su salida cada vez que un despliegue recrea el contenedor: además,
    van a un volumen, en un archivo por día y con la hora de Panamá."""
    entorno = dict(v.split("=", 1) for v in SERVICIOS["backend"]["environment"])
    assert _montajes("backend").get(entorno["LOG_CARPETA"]) == "registros" and "registros" in COMPOSE["volumes"]
    assert entorno["LOG_DIAS"] == "${LOG_DIAS:-90}"
    assert entorno["TZ"] == SERVICIOS["frontend"]["environment"]["TZ"] == "EST5"
    # El volumen nuevo copia el dueño que la carpeta tiene en la imagen.
    assert re.search(rf"mkdir -p [^\n]*{entorno['LOG_CARPETA']}\b", _dockerfile("backend"))
    assert re.search(rf"chown -R argonavis:argonavis [^\n]*{entorno['LOG_CARPETA']}\b", _dockerfile("backend"))

    # Los accesos de nginx, también: con la fecha en el nombre no hace falta rotarlos.
    [carpeta] = re.findall(r"^\s*access_log (\S+)/acceso-\$dia\.log main;", NGINX, re.M)
    assert _montajes("frontend").get(carpeta) == "registros_nginx" and "registros_nginx" in COMPOSE["volumes"]
    assert re.search(rf"mkdir -p [^\n]*{carpeta}\b", _dockerfile("frontend"))
    assert re.search(rf"chown -R nginx:nginx [^\n]*{carpeta}\b", _dockerfile("frontend"))
    # Y siguen en la salida de Docker (docker logs).
    assert re.search(r"^\s*access_log /var/log/nginx/access\.log main;", NGINX, re.M)
    # Con una variable en el nombre, nginx no escribe si la raíz de la petición no existe:
    # va en el server, para que valga también en /api/ (que no tiene carpeta).
    servidor = NGINX[NGINX.index("server {"):NGINX.index("location ")]
    assert re.search(r"^\s*root /usr/share/nginx/html;", servidor, re.M)


def test_la_integracion_continua_levanta_esta_misma_pila():
    ci = yaml.safe_load((RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    trabajo = ci["jobs"]["contenedores"]
    assert trabajo["env"]["COMPOSE_FILE"] == "docker-compose-prod.yml"
    pasos = "\n".join(paso.get("run", "") for paso in trabajo["steps"])
    assert "docker compose up -d --build --wait" in pasos
    for guion in ("verificar-despliegue.sh --solo-la-pila", "bash backup.sh", "bash probar-restauracion.sh", "vigilar.py"):
        assert guion in pasos, guion


def test_la_carpeta_temporal_de_nginx_es_de_su_usuario():
    """En la imagen oficial es de root: el volumen nuevo copia su dueño del Dockerfile."""
    antes_de_user = _dockerfile("frontend").split("USER nginx")[0]
    assert re.search(r"chown -R nginx:nginx /var/cache/nginx", antes_de_user)
