#!/usr/bin/env python3
"""ARGO NAVIS (SNM) — Vigilancia del servidor: avisa por correo cuando algo falla (2026-11-22).

Corre en el servidor y no en un contenedor: si el backend o Docker se caen, tiene que poder
avisar. Usa solo la biblioteca estándar del Python que trae Rocky (3.9) y el mismo correo
de la aplicación (.env).

  - Cada 5 minutos mira los contenedores, la aplicación, el certificado HTTPS, la base, los
    correos, los respaldos, el disco, la memoria y el reloj. No cambia nada ni deja rastro. Avisa cuando
    algo falla dos veces seguidas (en un despliegue los contenedores se reinician), no
    repite mientras sigue igual, lo recuerda una vez al día y avisa cuando se resuelve.
  - Con --diario corre verificar-despliegue.sh y manda el resultado si algo falla. Los
    lunes lo manda siempre, para saber que la vigilancia sigue viva, y además prueba que
    el último respaldo se puede restaurar (probar-restauracion.sh).
  - Con --probar manda un correo de prueba.

Instalación (una sola vez): CORREO_ALERTAS en el .env y, en el cron de root
(sudo crontab -e), con la ruta del repositorio:
  */5 * * * * python3 -I /home/vperez/argonavis/vigilar.py >> /var/log/argonavis-vigilancia.log 2>&1
  0 7 * * *   python3 -I /home/vperez/argonavis/vigilar.py --diario >> /var/log/argonavis-vigilancia.log 2>&1

Lo que no puede ver: si se apaga el servidor entero, nadie avisa desde adentro. Para eso, el
monitoreo de la DTI tiene que consultar <APP_URL>/api/health desde otro equipo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

try:
    import fcntl   # solo Linux
except ImportError:
    fcntl = None

RAIZ = Path(__file__).resolve().parent
ESTADO = Path("/var/lib/argonavis/vigilancia.json")
PANAMA = timezone(timedelta(hours=-5))
CONTENEDORES = ("argonavis_postgres", "argonavis_backend", "argonavis_frontend")

VECES_PARA_AVISAR = 2                   # seguidas: una sola puede ser un reinicio
RECORDATORIO = timedelta(hours=24)
DISCO_MAXIMO = 85                       # %
MEMORIA_MINIMA_MB = 150
RESPALDO_MAXIMO_HORAS = 26
CORREO_ATASCADO_HORAS = 2
ERRORES_POR_HORA = 20
CERTIFICADO_DIAS = 21                   # antes de que venza: lo que tarda la DTI en dar otro

_CONSULTA_CORREOS = (
    "SELECT count(*) FILTER (WHERE estado = 'fallido' AND creado_en > now() - interval '24 hours'), "
    f"count(*) FILTER (WHERE estado = 'pendiente' AND creado_en < now() - interval '{CORREO_ATASCADO_HORAS} hours') "
    "FROM correos_salida"
)


def usa_https(config: dict) -> bool:
    return config.get("USAR_HTTPS", "").strip().lower() == "true"


def vence_el(certificado: bytes) -> datetime:
    """Hasta cuándo vale un certificado (en DER): la segunda fecha que lleva; la primera es
    desde cuándo. Con dos cifras de año hasta 2049 y con cuatro desde 2050."""
    fechas = re.findall(rb"\x17\x0d(\d{12})Z|\x18\x0f(\d{14})Z", certificado)
    if len(fechas) < 2:
        raise ValueError("no es un certificado")
    corta, larga = fechas[1]
    texto = (larga or b"20" + corta).decode()
    return datetime.strptime(texto, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _ca_del_correo(config: dict) -> str | None:
    """La CA interna, en el servidor: MAIL_CA_CERT dice su ruta dentro del contenedor."""
    nombre = config.get("MAIL_CA_CERT", "").replace("/certificados/ca/", "", 1)
    ruta = RAIZ / "certificados" / "ca" / nombre
    return str(ruta) if nombre and ruta.is_file() else None


class Sistema:
    """Lo que se mira del servidor. Las pruebas lo reemplazan por uno de mentira."""

    def __init__(self, puerto_http: int = 80, puerto_https: int = 443) -> None:
        self.puerto_http, self.puerto_https = puerto_http, puerto_https

    @staticmethod
    def _sin_validar() -> ssl.SSLContext:
        """Se entra por «localhost», que no es el nombre del certificado: aquí no se valida."""
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
        return contexto

    def orden(self, *partes: str, espera: int = 30, juntar: bool = False) -> tuple[int, str]:
        """(código, salida) de un programa; 127 si no existe o no termina a tiempo."""
        try:
            r = subprocess.run(
                partes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if juntar else subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, timeout=espera, encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.TimeoutExpired):
            return 127, ""
        return r.returncode, r.stdout.strip()

    def salud(self, https: bool = False) -> str:
        """Vacío si la aplicación responde bien (nginx, backend y base); si no, el motivo."""
        base = f"https://localhost:{self.puerto_https}" if https else f"http://localhost:{self.puerto_http}"
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=20,
                                        context=self._sin_validar() if https else None) as r:
                estado = json.load(r).get("estado")
            return "" if estado == "ok" else f"responde «{estado}»"
        except urllib.error.HTTPError as e:
            try:
                return f"{e.code}: {json.load(e).get('estado')}"
            except ValueError:
                return f"responde {e.code}"
        except (OSError, ValueError) as e:
            return f"no responde ({getattr(e, 'reason', None) or type(e).__name__})"

    def vencimiento_certificado(self) -> datetime:
        """El del que nginx está usando: si se cambió el archivo y no se recargó, sigue el viejo."""
        with socket.create_connection(("localhost", self.puerto_https), timeout=20) as conexion:
            with self._sin_validar().wrap_socket(conexion, server_hostname="localhost") as tls:
                return vence_el(tls.getpeercert(binary_form=True) or b"")

    def disco(self, carpeta: str) -> tuple[int, int]:
        """(% usado, MB libres) del disco donde está la carpeta."""
        uso = shutil.disk_usage(carpeta)
        return round(100 * (uso.total - uso.free) / uso.total), uso.free // 2**20

    def memoria_disponible(self) -> int | None:
        """MB, o None si no se sabe."""
        try:
            m = re.search(r"^MemAvailable:\s+(\d+) kB", Path("/proc/meminfo").read_text(), re.M)
        except OSError:
            return None
        return int(m.group(1)) // 1024 if m else None

    def enviar(self, config: dict, mensaje: EmailMessage) -> None:
        """Por el servidor de correo de la aplicación, con el TLS que ella use."""
        verdadero = {k for k in ("MAIL_USAR_SSL", "MAIL_STARTTLS") if config.get(k, "").lower() == "true"}
        servidor, puerto = config["MAIL_HOST"], int(config.get("MAIL_PORT") or 25)
        if "MAIL_USAR_SSL" in verdadero:
            conexion = smtplib.SMTP_SSL(servidor, puerto, timeout=20, context=ssl.create_default_context(cafile=_ca_del_correo(config)))
        else:
            conexion = smtplib.SMTP(servidor, puerto, timeout=20)
        with conexion as smtp:
            if "MAIL_STARTTLS" in verdadero:
                smtp.starttls(context=ssl.create_default_context(cafile=_ca_del_correo(config)))
            if config.get("MAIL_USERNAME"):
                smtp.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
            smtp.send_message(mensaje)


def leer_env(ruta: Path) -> dict[str, str]:
    """Las variables del .env, como las lee Docker: la última manda, sin las comillas que las
    rodean y, sin comillas, sin el comentario del final."""
    config: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z_]\w*)=(.*)$", linea.strip())
        if m:
            entre_comillas = re.match(r"""^\s*(["'])(.*?)\1(?:\s+#.*)?$""", m.group(2))
            if entre_comillas:
                valor = entre_comillas.group(2)
            else:
                valor = re.split(r"(?:^|\s)#", m.group(2), maxsplit=1)[0].strip()
            config[m.group(1)] = valor
    return config


def destinatarios(config: dict) -> list[str]:
    return [d.strip() for d in config.get("CORREO_ALERTAS", "").split(",") if d.strip()]


# ── Qué mira ──────────────────────────────────────────────────────────────────

def revisar(sistema: Sistema, config: dict, ahora: datetime) -> dict[str, str]:
    """{qué: por qué} de lo que está fallando."""
    fallas: dict[str, str] = {}
    for mirar in (_contenedores, _aplicacion, _certificado, _correos, _procesos, _errores, _respaldos, _discos, _equipo):
        fallas.update(mirar(sistema, config, ahora))
    return fallas


def _contenedores(sistema, config, ahora) -> dict[str, str]:
    fallas = {}
    formato = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}|{{.State.OOMKilled}}"
    for nombre in CONTENEDORES:
        codigo, salida = sistema.orden("docker", "inspect", "-f", formato, nombre)
        estado, salud, sin_memoria = (salida.split("|") + ["", "", ""])[:3]
        motivo = ""
        if codigo:
            motivo = f"{nombre} no existe o Docker no responde."
        elif estado != "running":
            motivo = f"{nombre} no está en marcha ({estado}): docker logs --tail 100 {nombre}"
        elif salud == "unhealthy":
            motivo = f"{nombre} no está sano: docker logs --tail 100 {nombre}"
        elif sin_memoria == "true":
            motivo = f"Docker cortó a {nombre} por falta de memoria: súbele el límite en el .env."
        if motivo:
            fallas[f"contenedor {nombre}"] = motivo
    return fallas


def _aplicacion(sistema, config, ahora) -> dict[str, str]:
    motivo = sistema.salud(https=usa_https(config))
    return {"aplicación": f"La aplicación no funciona: {motivo}."} if motivo else {}


def _certificado(sistema, config, ahora) -> dict[str, str]:
    """El certificado HTTPS, antes de que venza: vencido, el navegador no deja entrar a nadie."""
    if not usa_https(config):
        return {}
    try:
        vence = sistema.vencimiento_certificado().astimezone(PANAMA)
    except (OSError, ValueError) as e:   # ssl.SSLError es un OSError
        return {"certificado": f"No se pudo leer el certificado HTTPS del 443 ({type(e).__name__})."}
    dias = (vence.date() - ahora.astimezone(PANAMA).date()).days
    if vence <= ahora:
        cuando = f"venció el {vence:%d/%m/%Y}: los navegadores no dejan entrar"
    elif dias > CERTIFICADO_DIAS:
        return {}
    else:
        cuando = "vence hoy" if dias == 0 else f"vence el {vence:%d/%m/%Y} (en {dias} día{'' if dias == 1 else 's'})"
    return {"certificado": f"El certificado HTTPS {cuando}. Cómo cambiarlo: README → HTTPS."}


def _correos(sistema, config, ahora) -> dict[str, str]:
    codigo, salida = sistema.orden(
        "docker", "exec", "argonavis_postgres", "sh", "-c",
        f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -F "|" -c "{_CONSULTA_CORREOS}"')
    m = re.fullmatch(r"(\d+)\|(\d+)", salida)
    if codigo or not m:
        return {"base": "No se pudo consultar la base de datos."}
    fallidos, atascados = int(m.group(1)), int(m.group(2))
    fallas = {}
    if fallidos:
        fallas["correos fallidos"] = (
            f"{fallidos} correo(s) no se pudieron entregar en las últimas 24 h. Para ver el motivo: "
            "select numero, asunto, ultimo_error from correos_salida where estado = 'fallido';")
    if atascados:
        fallas["cola de correos"] = f"{atascados} correo(s) llevan más de {CORREO_ATASCADO_HORAS} h sin salir."
    return fallas


def _procesos(sistema, config, ahora) -> dict[str, str]:
    _, salida = sistema.orden("docker", "logs", "--since", "10m", "argonavis_backend", juntar=True)
    caidos = len(re.findall(r"Child process .* died", salida))
    return {"procesos": f"Se cayeron {caidos} proceso(s) del backend en los últimos 10 minutos (¿memoria?)."} if caidos else {}


def _errores(sistema, config, ahora) -> dict[str, str]:
    """Una racha de errores en el archivo del día (el contenedor lleva la hora de Panamá)."""
    _, salida = sistema.orden(
        "docker", "exec", "argonavis_backend", "sh", "-c", "tail -n 20000 /app/registros/argonavis-$(date +%F).log")
    desde = (ahora.astimezone(PANAMA) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    cuantos = sum(
        1 for linea in salida.splitlines()
        if re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+ (ERROR|CRITICAL) ", linea) and linea[:19] >= desde
    )
    return {"errores": f"{cuantos} errores en el registro del backend en la última hora."} if cuantos >= ERRORES_POR_HORA else {}


def _carpeta_respaldos(sistema) -> Path | None:
    """La del cron de root (DIR_BACKUPS=… bash backup.sh), o None si no hay respaldo programado."""
    _, salida = sistema.orden("crontab", "-l")
    for linea in salida.splitlines():
        if "backup.sh" in linea and not linea.lstrip().startswith("#"):
            m = re.search(r"DIR_BACKUPS=(\S+)", linea)
            return Path(m.group(1) if m else "/root/backups")
    return None


def _respaldos(sistema, config, ahora) -> dict[str, str]:
    carpeta = _carpeta_respaldos(sistema)
    if carpeta is None:
        return {"respaldo": "No hay respaldo programado en el cron de root (backup.sh)."}
    fallas = {}
    for clave, ninguno, ultimo, encontrados in (
        ("respaldo de la base", "ningún respaldo de la base", "El último respaldo de la base",
         list(carpeta.glob("argonavis_bd_*.sql.gz"))),
        ("respaldo de los documentos", "ninguna copia de los documentos", "La última copia de los documentos",
         list((carpeta / "documentos").glob("20*"))),
    ):
        if not encontrados:
            fallas[clave] = f"No hay {ninguno} en {carpeta}."
            continue
        horas = (time.time() - max(e.stat().st_mtime for e in encontrados)) / 3600
        if horas > RESPALDO_MAXIMO_HORAS:
            fallas[clave] = f"{ultimo} tiene {horas:.0f} h: ¿corrió el cron? (backup.log)"
    return fallas


def _discos(sistema, config, ahora) -> dict[str, str]:
    """El de Docker, el del sistema y el de los respaldos (en Rocky suelen ser distintos)."""
    fallas = {}
    carpeta = _carpeta_respaldos(sistema)
    for ruta in {"/", "/var/lib/docker", str(carpeta or "/")}:
        try:
            usado, libres = sistema.disco(ruta)
        except OSError:
            continue
        if usado >= DISCO_MAXIMO:
            fallas[f"disco {ruta}"] = f"El disco de {ruta} está al {usado} % (quedan {libres} MB)."
    return fallas


def _equipo(sistema, config, ahora) -> dict[str, str]:
    fallas = {}
    memoria = sistema.memoria_disponible()
    if memoria is not None and memoria < MEMORIA_MINIMA_MB:
        fallas["memoria"] = f"Al servidor le quedan {memoria} MB de memoria."
    codigo, salida = sistema.orden("timedatectl", "show", "-p", "NTPSynchronized", "--value")
    if codigo == 0 and salida == "no":
        fallas["reloj"] = "El reloj del servidor no está sincronizado (los plazos dependen de la hora)."
    return fallas


# ── Cuándo avisa ──────────────────────────────────────────────────────────────

def _leer_estado(ruta: Path) -> dict[str, dict]:
    try:
        fallas = json.loads(ruta.read_text(encoding="utf-8"))["fallas"]
        return fallas if isinstance(fallas, dict) else {}
    except (OSError, ValueError, KeyError, TypeError):
        return {}   # la primera vez, o dañado: se empieza de nuevo


def _guardar_estado(ruta: Path, fallas: dict[str, dict], ahora: datetime) -> None:
    ruta.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    nuevo = ruta.with_suffix(".nuevo")
    nuevo.write_text(json.dumps({"ultima": ahora.isoformat(), "fallas": fallas}, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(nuevo, ruta)


def vuelta(sistema: Sistema, config: dict, ruta_estado: Path, ahora: datetime) -> int:
    """Una pasada. Devuelve cuántas cosas están fallando."""
    antes, fallas = _leer_estado(ruta_estado), revisar(sistema, config, ahora)
    estado: dict[str, dict] = {}
    nuevas, recordadas = [], []
    for clave, motivo in fallas.items():
        falla = {"desde": ahora.isoformat(), "veces": 0, "avisada": None, **antes.get(clave, {})}
        falla["veces"] += 1
        falla["motivo"] = motivo
        estado[clave] = falla
        if falla["avisada"] is None:
            if falla["veces"] >= VECES_PARA_AVISAR:
                nuevas.append(clave)
        elif ahora - datetime.fromisoformat(falla["avisada"]) >= RECORDATORIO:
            recordadas.append(clave)
    resueltas = {clave: falla for clave, falla in antes.items() if clave not in fallas and falla.get("avisada")}

    if fallas:
        print(f"[{ahora:%F %T}] " + " | ".join(fallas.values()), flush=True)
    if nuevas or recordadas or resueltas:
        por_contar = {clave: falla for clave, falla in estado.items() if falla["avisada"] or clave in nuevas}
        if _avisar(sistema, config, *_redactar(por_contar, nuevas, recordadas, resueltas, ahora), ahora):
            for clave in nuevas + recordadas:
                estado[clave]["avisada"] = ahora.isoformat()
        else:
            estado.update(resueltas)   # se vuelve a intentar en la próxima
    _guardar_estado(ruta_estado, estado, ahora)
    return len(fallas)


def _redactar(actuales, nuevas, recordadas, resueltas, ahora) -> tuple[str, str]:
    cuerpo = []
    if actuales:
        cuerpo.append("PROBLEMAS")
        for falla in actuales.values():
            cuerpo.append(f"- {falla['motivo']} (desde el {datetime.fromisoformat(falla['desde']):%d/%m a las %H:%M})")
        cuerpo.append("")
    if resueltas:
        cuerpo.append("RESUELTOS")
        cuerpo += [f"- {falla.get('motivo', clave)}" for clave, falla in resueltas.items()]
        cuerpo.append("")
    if actuales:
        cuerpo += ["Para ver el detalle, en el servidor: sudo bash verificar-despliegue.sh", ""]
    if nuevas:
        asunto = f"{len(actuales)} problema(s): {', '.join(actuales)}"
    elif actuales:
        asunto = f"sigue(n) {len(actuales)} problema(s): {', '.join(actuales)}"
    else:
        asunto = f"resuelto: {', '.join(resueltas)}"
    return asunto, "\n".join(cuerpo)


# ── El correo ─────────────────────────────────────────────────────────────────

def armar_correo(config: dict, asunto: str, cuerpo: str, ahora: datetime) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["Subject"] = " ".join(asunto.split())   # sin saltos de línea
    mensaje["From"] = config.get("MAIL_FROM", "")
    mensaje["To"] = ", ".join(destinatarios(config))
    mensaje["Date"] = format_datetime(ahora)
    mensaje["Auto-Submitted"] = "auto-generated"
    mensaje.set_content(cuerpo)
    return mensaje


def _avisar(sistema: Sistema, config: dict, asunto: str, cuerpo: str, ahora: datetime) -> bool:
    """Si el correo salió. Si no, dice por qué (sin claves) y se reintenta en la próxima."""
    if not destinatarios(config) or not config.get("MAIL_HOST"):
        print(f"[{ahora:%F %T}] Sin CORREO_ALERTAS (o sin MAIL_HOST) en el .env: no se avisa a nadie.", flush=True)
        return False
    equipo = socket.gethostname()
    encabezado = f"Servidor: {equipo}   {ahora.astimezone(PANAMA):%d/%m/%Y %H:%M} (hora de Panamá)\n\n"
    try:
        sistema.enviar(config, armar_correo(config, f"[ARGO NAVIS] {equipo}: {asunto}", encabezado + cuerpo, ahora))
    except (OSError, smtplib.SMTPException) as e:   # ssl.SSLError es un OSError
        print(f"[{ahora:%F %T}] No se pudo enviar el aviso «{asunto}»: {type(e).__name__}: {e}", flush=True)
        return False
    print(f"[{ahora:%F %T}] Aviso enviado: {asunto}", flush=True)
    return True


def probar(sistema: Sistema, config: dict, ahora: datetime) -> int:
    cuerpo = "Correo de prueba de la vigilancia de ARGO NAVIS: si lo lees, los avisos llegan.\n"
    return 0 if _avisar(sistema, config, "correo de prueba", cuerpo, ahora) else 1


# ── El resumen del día ────────────────────────────────────────────────────────

def diario(sistema: Sistema, config: dict, ahora: datetime) -> int:
    """La revisión completa. Manda el resultado si algo falla y, los lunes, siempre."""
    lunes = ahora.astimezone(PANAMA).weekday() == 0
    _, salida = sistema.orden("bash", str(RAIZ / "verificar-despliegue.sh"), "--diario", espera=900, juntar=True)
    if "Resultado:" not in salida:
        salida += "\n  [FALLA] La revisión del día no se pudo correr (verificar-despliegue.sh --diario)."
    if lunes:
        codigo, restauracion = sistema.orden("bash", str(RAIZ / "probar-restauracion.sh"), espera=3600, juntar=True)
        salida += "\n\n== Prueba de restauración del último respaldo ==\n" + restauracion
        if codigo:
            salida += "\n  [FALLA] El último respaldo no se pudo restaurar: hay que revisarlo hoy."
    lineas = [linea.strip() for linea in salida.splitlines()]
    fallas = [linea for linea in lineas if linea.startswith("[FALLA]")]
    avisos = [linea for linea in lineas if linea.startswith("[AVISO]")]

    sistema.orden("docker", "exec", "argonavis_frontend", "find", "/var/log/argonavis", "-name", "acceso-*.log",
                  "-mtime", f"+{int(config.get('LOG_DIAS') or 90)}", "-delete")

    if fallas or lunes:
        asunto = f"{len(fallas)} falla(s) en la revisión del día" if fallas else "revisión semanal, todo bien"
        cuerpo = "\n".join([*fallas, *avisos, "", "Revisión completa:", salida, ""])
        _avisar(sistema, config, asunto, cuerpo, ahora)
    return 1 if fallas else 0


def main(argumentos: list[str] | None = None) -> int:
    partes = argparse.ArgumentParser(description="Vigila ARGO NAVIS y avisa por correo cuando algo falla.")
    modo = partes.add_mutually_exclusive_group()
    modo.add_argument("--diario", action="store_true", help="la revisión completa (una vez al día)")
    modo.add_argument("--probar", action="store_true", help="manda un correo de prueba")
    opciones = partes.parse_args(argumentos)

    if not (RAIZ / ".env").exists():
        print(f"Falta {RAIZ / '.env'}.")
        return 2
    config, ahora, sistema = leer_env(RAIZ / ".env"), datetime.now(PANAMA), Sistema()
    if opciones.probar:
        return probar(sistema, config, ahora)
    if opciones.diario:
        return diario(sistema, config, ahora)

    ESTADO.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(ESTADO.with_suffix(".candado"), "w") as candado:
        if fcntl:
            try:
                fcntl.flock(candado, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return 0   # la vuelta anterior sigue en curso
        return 1 if vuelta(sistema, config, ESTADO, ahora) else 0


if __name__ == "__main__":
    sys.exit(main())
