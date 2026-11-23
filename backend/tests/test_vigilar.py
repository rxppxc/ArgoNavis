"""La vigilancia del servidor (vigilar.py, 2026-11-22): avisa por correo cuando algo falla.

Corre en el servidor y no en un contenedor: si el backend se cae, tiene que poder avisar.
Aquí el servidor es de mentira: un sistema sano al que cada prueba le rompe algo."""
import ast
import importlib.util
import json
import os
import smtplib
import ssl
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from ayudas import programa

RAIZ = Path(__file__).resolve().parents[2]


def _cargar():
    especificacion = importlib.util.spec_from_file_location("vigilar", RAIZ / "vigilar.py")
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


vigilar = _cargar()
PANAMA = timezone(timedelta(hours=-5))
AHORA = datetime(2026, 11, 24, 14, 5, tzinfo=PANAMA)   # martes
CADA = timedelta(minutes=5)

CONFIG = {
    "CORREO_ALERTAS": "soporte@migracion.gob.pa, otro@migracion.gob.pa",
    "MAIL_HOST": "correo.prueba.local", "MAIL_FROM": "no-reply@migracion.gob.pa",
    "MAIL_USERNAME": "cuenta", "MAIL_PASSWORD": "clave-secreta",
}
CON_HTTPS = {**CONFIG, "USAR_HTTPS": "true"}


class Servidor(vigilar.Sistema):
    """Un servidor donde todo está bien."""

    def __init__(self, respaldos: Path):
        self.respaldos = respaldos
        self.enviados, self.ordenes = [], []
        self.motivo_salud, self.error_de_correo = "", None
        self.uso, self.memoria = 40, 1500
        self.por_https, self.vence = None, ConnectionRefusedError("[Errno 111] Connection refused")
        self.respuestas = {
            "docker inspect": (0, "running|healthy|false"),
            "correos_salida": (0, "0|0"),
            "docker logs": (0, "INFO: todo tranquilo"),
            "/app/registros": (0, ""),
            "timedatectl": (0, "yes"),
            "crontab -l": (0, f"0 2 * * * DIR_BACKUPS={respaldos} bash /x/backup.sh >> /x/backup.log 2>&1"),
            "verificar-despliegue.sh --diario": (0, "  [OK]    todo\n\nResultado: todo bien (0 aviso/s)."),
            "probar-restauracion.sh": (0, "Resultado: el respaldo se restaura."),
            "find /var/log/argonavis": (0, ""),
        }
        self.poner_respaldo(horas=10)

    def poner_respaldo(self, horas: float):
        base = self.respaldos / "argonavis_bd_2026-11-24_020000.sql.gz"
        copia = self.respaldos / "documentos" / "2026-11-24_020000"
        copia.mkdir(parents=True, exist_ok=True)
        base.write_bytes(b"x")
        momento = time.time() - horas * 3600
        os.utime(base, (momento, momento))
        os.utime(copia, (momento, momento))

    def orden(self, *partes, espera=30, juntar=False):
        texto = " ".join(partes)
        self.ordenes.append(texto)
        for patron, respuesta in self.respuestas.items():
            if patron in texto:
                return respuesta
        raise AssertionError(f"orden no esperada: {texto}")

    def salud(self, https=False):
        self.por_https = https
        return self.motivo_salud

    def vencimiento_certificado(self):
        if isinstance(self.vence, Exception):
            raise self.vence
        return self.vence

    def disco(self, carpeta):
        return self.uso, 9000

    def memoria_disponible(self):
        return self.memoria

    def enviar(self, config, mensaje):
        if self.error_de_correo:
            raise self.error_de_correo
        self.enviados.append(mensaje)


@pytest.fixture
def servidor(tmp_path):
    return Servidor(tmp_path / "respaldos")


@pytest.fixture
def vuelta(servidor, tmp_path):
    """Da una vuelta de la vigilancia, `minutos` después de la primera."""
    def correr(minutos: float = 0, config: dict = CONFIG):
        return vigilar.vuelta(servidor, config, tmp_path / "estado.json", AHORA + timedelta(minutes=minutos))
    return correr


def _texto(mensaje) -> str:
    return mensaje.get_content()


# ── Cuándo avisa ──────────────────────────────────────────────────────────────

def test_si_todo_esta_bien_no_avisa(servidor, vuelta):
    assert vuelta() == 0 and vuelta(5) == 0
    assert servidor.enviados == []


def test_una_falla_de_paso_no_avisa(servidor, vuelta):
    """Durante un despliegue los contenedores se reinician: se avisa a la segunda seguida."""
    servidor.motivo_salud = "no responde"
    assert vuelta() == 1
    servidor.motivo_salud = ""
    vuelta(5)
    servidor.motivo_salud = "no responde"
    vuelta(10)
    assert servidor.enviados == []


def test_avisa_una_vez_recuerda_cada_dia_y_dice_cuando_se_resuelve(servidor, vuelta):
    servidor.motivo_salud = "no responde"
    vuelta()
    vuelta(5)
    [aviso] = servidor.enviados
    assert "problema" in aviso["Subject"] and "aplicación" in aviso["Subject"]
    assert "no responde" in _texto(aviso) and "14:05" in _texto(aviso), "dice qué falla y desde cuándo"
    assert aviso["To"] == "soporte@migracion.gob.pa, otro@migracion.gob.pa"

    for minutos in range(10, 24 * 60, 5):
        vuelta(minutos)
    assert len(servidor.enviados) == 1, "mientras sigue igual, no repite"
    vuelta(24 * 60 + 10)
    assert len(servidor.enviados) == 2 and "sigue" in servidor.enviados[1]["Subject"]

    servidor.motivo_salud = ""
    vuelta(24 * 60 + 15)
    assert len(servidor.enviados) == 3 and "resuelto" in servidor.enviados[2]["Subject"]
    vuelta(24 * 60 + 20)
    assert len(servidor.enviados) == 3


def test_una_falla_nueva_avisa_aunque_haya_otra_ya_avisada(servidor, vuelta):
    servidor.motivo_salud = "no responde"
    vuelta()
    vuelta(5)
    servidor.uso = 93
    vuelta(10)
    vuelta(15)
    assert len(servidor.enviados) == 2
    assert "no responde" in _texto(servidor.enviados[1]) and "93" in _texto(servidor.enviados[1]), "y cuenta las dos"


def test_si_el_correo_falla_se_vuelve_a_intentar(servidor, vuelta, capsys):
    servidor.motivo_salud = "no responde"
    servidor.error_de_correo = smtplib.SMTPServerDisconnected("caído")
    vuelta()
    vuelta(5)
    servidor.error_de_correo = None
    vuelta(10)
    assert len(servidor.enviados) == 1
    # También el de que se resolvió.
    servidor.motivo_salud, servidor.error_de_correo = "", ConnectionRefusedError()
    vuelta(15)
    servidor.error_de_correo = None
    vuelta(20)
    assert len(servidor.enviados) == 2 and "resuelto" in servidor.enviados[1]["Subject"]
    assert "clave-secreta" not in capsys.readouterr().out


def test_sin_correo_configurado_lo_dice_y_no_da_por_avisado(servidor, vuelta, capsys):
    servidor.motivo_salud = "no responde"
    sin_correo = {**CONFIG, "CORREO_ALERTAS": ""}
    vuelta(0, sin_correo)
    vuelta(5, sin_correo)
    assert servidor.enviados == [] and "CORREO_ALERTAS" in capsys.readouterr().out
    vuelta(10)   # ya configurado, avisa enseguida
    assert len(servidor.enviados) == 1


def test_un_estado_danado_no_detiene_la_vigilancia(servidor, vuelta, tmp_path):
    (tmp_path / "estado.json").write_text("{esto no es json", encoding="utf-8")
    servidor.motivo_salud = "no responde"
    vuelta()
    vuelta(5)
    assert len(servidor.enviados) == 1


# ── Qué mira ──────────────────────────────────────────────────────────────────

def _revisar(servidor) -> str:
    return "\n".join(vigilar.revisar(servidor, CONFIG, AHORA).values())


def test_en_un_servidor_sano_no_encuentra_nada(servidor):
    assert vigilar.revisar(servidor, CONFIG, AHORA) == {}


@pytest.mark.parametrize(("orden", "respuesta", "dice"), [
    ("docker inspect", (0, "exited||false"), "argonavis_backend no está en marcha"),
    ("docker inspect", (0, "running|unhealthy|false"), "argonavis_backend no está sano"),
    ("docker inspect", (0, "running|healthy|true"), "por falta de memoria"),
    ("docker inspect", (1, ""), "argonavis_backend no existe"),
    ("correos_salida", (0, "3|0"), "3 correo(s) no se pudieron entregar"),
    ("correos_salida", (0, "0|2"), "2 correo(s) llevan más de"),
    ("correos_salida", (2, ""), "No se pudo consultar la base"),
    ("docker logs", (0, "x\nINFO:     Child process [33] died\nINFO:     Child process [34] died"), "2 proceso(s) del backend"),
    ("timedatectl", (0, "no"), "reloj"),
    ("crontab -l", (1, ""), "No hay respaldo programado"),
    ("crontab -l", (0, "# 0 2 * * * bash /x/backup.sh"), "No hay respaldo programado"),
])
def test_encuentra_lo_que_falla(servidor, orden, respuesta, dice):
    servidor.respuestas[orden] = respuesta
    assert dice in _revisar(servidor)


def test_un_contenedor_que_esta_arrancando_no_es_una_falla(servidor):
    servidor.respuestas["docker inspect"] = (0, "running|starting|false")
    assert vigilar.revisar(servidor, CONFIG, AHORA) == {}


def test_la_aplicacion_el_disco_y_la_memoria(servidor):
    servidor.motivo_salud = "503: sin base de datos"
    servidor.uso, servidor.memoria = 91, 60
    encontrado = _revisar(servidor)
    assert "503: sin base de datos" in encontrado and "91 %" in encontrado and "60 MB" in encontrado


def test_sin_https_no_mira_el_certificado(servidor):
    """En el 443 no contesta nadie, y está bien."""
    assert vigilar.revisar(servidor, CONFIG, AHORA) == {} and servidor.por_https is False
    assert vigilar.revisar(servidor, {**CONFIG, "USAR_HTTPS": "false"}, AHORA) == {}


@pytest.mark.parametrize(("dias", "dice"), [
    (90, None), (22, None),
    (21, "vence el 15/12/2026 (en 21 días)"), (1, "vence el 25/11/2026 (en 1 día)"),
    (0, "vence hoy"), (-2, "venció el 22/11/2026"),
])
def test_avisa_antes_de_que_venza_el_certificado(servidor, dias, dice):
    """Vencido, el navegador no deja entrar a nadie; con tiempo, la DTI alcanza a dar otro."""
    servidor.vence = AHORA + timedelta(days=dias, hours=1 if dias >= 0 else 0)
    fallas = vigilar.revisar(servidor, CON_HTTPS, AHORA)
    assert servidor.por_https is True, "la aplicación se consulta por donde atiende"
    if dice is None:
        assert fallas == {}
    else:
        assert list(fallas) == ["certificado"] and dice in fallas["certificado"] and "README" in fallas["certificado"]


@pytest.mark.parametrize("error", [ConnectionRefusedError("x"), TimeoutError("x"), ssl.SSLError("x"), ValueError("x")])
def test_si_el_certificado_no_se_puede_leer_lo_dice(servidor, error):
    servidor.vence = error
    assert "No se pudo leer el certificado" in vigilar.revisar(servidor, CON_HTTPS, AHORA)["certificado"]


def test_los_respaldos_viejos_o_que_faltan(servidor):
    servidor.poner_respaldo(horas=30)
    encontrado = _revisar(servidor)
    assert "El último respaldo de la base tiene 30 h" in encontrado
    assert "La última copia de los documentos tiene 30 h" in encontrado
    (servidor.respaldos / "argonavis_bd_2026-11-24_020000.sql.gz").unlink()
    (servidor.respaldos / "documentos" / "2026-11-24_020000").rmdir()
    encontrado = _revisar(servidor)
    assert "No hay ningún respaldo de la base" in encontrado and "No hay ninguna copia de los documentos" in encontrado


def test_muchos_errores_en_una_hora(servidor):
    """Uno suelto va en el resumen del día; una racha es un incidente."""
    def lineas(cuantas: int, minutos: int) -> str:
        hora = (AHORA - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S,000")
        return "\n".join(f"{hora} ERROR [app] [abc] algo falló\nTraceback (most recent call last):" for _ in range(cuantas))

    servidor.respuestas["/app/registros"] = (0, lineas(19, 5) + "\n" + lineas(50, 90))
    assert vigilar.revisar(servidor, CONFIG, AHORA) == {}, "los de hace más de una hora no cuentan"
    servidor.respuestas["/app/registros"] = (0, lineas(20, 5))
    assert "20 errores" in _revisar(servidor)


# ── El correo ─────────────────────────────────────────────────────────────────

class _Smtp:
    def __init__(self, *args, **kwargs):
        self.llamadas.append((type(self).__name__, args[:2], "context" in kwargs))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, nombre):
        return lambda *args, **kwargs: self.llamadas.append((nombre, len(args), "context" in kwargs)) or {}


@pytest.mark.parametrize(("extra", "esperado"), [
    ({}, [("SMTP", ("correo.prueba.local", 25), False), ("login", 2, False), ("send_message", 1, False)]),
    ({"MAIL_STARTTLS": "true", "MAIL_PORT": "587"},
     [("SMTP", ("correo.prueba.local", 587), False), ("starttls", 0, True), ("login", 2, False), ("send_message", 1, False)]),
    ({"MAIL_USAR_SSL": "TRUE", "MAIL_PORT": "465"},
     [("SMTP_SSL", ("correo.prueba.local", 465), True), ("login", 2, False), ("send_message", 1, False)]),
    ({"MAIL_USERNAME": ""}, [("SMTP", ("correo.prueba.local", 25), False), ("send_message", 1, False)]),
], ids=["sin TLS", "STARTTLS", "SMTPS", "sin usuario"])
def test_usa_el_mismo_correo_que_la_aplicacion(monkeypatch, extra, esperado):
    llamadas = []
    monkeypatch.setattr(vigilar.smtplib, "SMTP", type("SMTP", (_Smtp,), {"llamadas": llamadas}))
    monkeypatch.setattr(vigilar.smtplib, "SMTP_SSL", type("SMTP_SSL", (_Smtp,), {"llamadas": llamadas}))
    config = {**CONFIG, **extra}
    vigilar.Sistema().enviar(config, vigilar.armar_correo(config, "Prueba", "Ñandú", AHORA))
    assert llamadas == esperado


@pytest.mark.parametrize(("ca", "esperada"), [
    ("/certificados/ca/snm.pem", "snm.pem"),   # la ruta dentro del contenedor; el archivo, en el servidor
    ("/certificados/ca/no-esta.pem", None), ("", None),
])
@pytest.mark.parametrize("tls", [{"MAIL_STARTTLS": "true"}, {"MAIL_USAR_SSL": "true"}], ids=["STARTTLS", "SMTPS"])
def test_el_correo_se_valida_con_la_ca_interna(monkeypatch, tmp_path, tls, ca, esperada):
    """Sin ella, con el correo por TLS no saldría ningún aviso."""
    carpeta = tmp_path / "certificados" / "ca"
    carpeta.mkdir(parents=True)
    (carpeta / "snm.pem").write_text("pem", encoding="utf-8")
    monkeypatch.setattr(vigilar, "RAIZ", tmp_path)
    for nombre in ("SMTP", "SMTP_SSL"):
        monkeypatch.setattr(vigilar.smtplib, nombre, type(nombre, (_Smtp,), {"llamadas": []}))
    usadas = []
    monkeypatch.setattr(vigilar.ssl, "create_default_context", lambda cafile=None: usadas.append(cafile))
    config = {**CONFIG, **tls, "MAIL_CA_CERT": ca}
    vigilar.Sistema().enviar(config, vigilar.armar_correo(config, "Prueba", "x", AHORA))
    assert usadas == [str(carpeta / esperada) if esperada else None]


def test_el_correo_lleva_tildes_y_no_lleva_secretos():
    mensaje = vigilar.armar_correo(CONFIG, "Atención: aplicación caída\r\nBcc: otro@x", "El año de la ñ", AHORA)
    assert mensaje["Subject"] == "Atención: aplicación caída Bcc: otro@x", "sin saltos de línea en el asunto"
    assert mensaje["From"] == "no-reply@migracion.gob.pa" and "El año de la ñ" in mensaje.get_content()
    assert "clave-secreta" not in mensaje.as_string()


def test_lee_el_env_como_docker(tmp_path):
    (tmp_path / ".env").write_text(
        "# comentario\nMAIL_HOST=correo.local\r\nCORREO_ALERTAS=\"a@x.pa, b@x.pa\"\n\nCLAVE=con=iguales#y-numeral\n"
        "MAIL_HOST=el-ultimo.local\nSUELTA\nUSAR_HTTPS=true   # desde hoy\nENTRE='a # b'\n"
        "CON_NOTA=\"a b\"  # nota\nVACIA=   # todavía no\n", encoding="utf-8")
    config = vigilar.leer_env(tmp_path / ".env")
    assert config == {"MAIL_HOST": "el-ultimo.local", "CORREO_ALERTAS": "a@x.pa, b@x.pa", "CLAVE": "con=iguales#y-numeral",
                      "USAR_HTTPS": "true", "ENTRE": "a # b", "CON_NOTA": "a b", "VACIA": ""}


# ── El resumen del día ────────────────────────────────────────────────────────

def test_el_resumen_del_dia_solo_si_algo_falla(servidor):
    assert vigilar.diario(servidor, CONFIG, AHORA) == 0
    assert servidor.enviados == []
    servidor.respuestas["verificar-despliegue.sh --diario"] = (
        1, "  [OK]    bien\n  [FALLA] Active Directory: sin respuesta\n  [AVISO] algo menor\n\nResultado: 1 falla/s y 1 aviso/s.")
    assert vigilar.diario(servidor, CONFIG, AHORA) == 1
    [resumen] = servidor.enviados
    assert "1 falla" in resumen["Subject"]
    assert "Active Directory: sin respuesta" in _texto(resumen) and "algo menor" in _texto(resumen)


def test_los_lunes_avisa_siempre_y_prueba_el_respaldo(servidor):
    """Para saber que la vigilancia sigue viva, y que el respaldo se puede restaurar."""
    lunes = AHORA - timedelta(days=1)
    assert vigilar.diario(servidor, CONFIG, lunes) == 0
    [resumen] = servidor.enviados
    assert "todo bien" in resumen["Subject"] and "el respaldo se restaura" in _texto(resumen)

    servidor.respuestas["probar-restauracion.sh"] = (1, "Resultado: NO se pudo restaurar.")
    assert vigilar.diario(servidor, CONFIG, lunes) == 1
    assert "falla" in servidor.enviados[1]["Subject"] and "NO se pudo restaurar" in _texto(servidor.enviados[1])
    assert not any("probar-restauracion" in o for o in _ordenes_de(servidor, AHORA)), "los demás días, no"


def _ordenes_de(servidor, cuando) -> list[str]:
    servidor.ordenes.clear()
    vigilar.diario(servidor, CONFIG, cuando)
    return servidor.ordenes


def test_si_la_verificacion_no_corre_tambien_avisa(servidor):
    servidor.respuestas["verificar-despliegue.sh --diario"] = (127, "")
    assert vigilar.diario(servidor, CONFIG, AHORA) == 1
    assert "no se pudo correr" in _texto(servidor.enviados[0])


def test_borra_los_accesos_viejos_de_nginx(servidor):
    borrado = [o for o in _ordenes_de(servidor, AHORA) if "find /var/log/argonavis" in o]
    assert borrado and "-mtime +90" in borrado[0] and "acceso-*.log" in borrado[0]
    servidor.ordenes.clear()
    vigilar.diario(servidor, {**CONFIG, "LOG_DIAS": "30"}, AHORA)
    assert any("-mtime +30" in o for o in servidor.ordenes)


# ── Un servidor HTTPS de verdad ───────────────────────────────────────────────

class _Salud(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/api/health" else 404)
        self.end_headers()
        self.wfile.write(json.dumps({"estado": "ok"}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor_https(tmp_path):
    """(puerto, cuándo vence) de un servidor con un certificado de otro nombre y firmado por él mismo."""
    openssl = programa("openssl")
    if openssl is None:
        pytest.skip("sin openssl")
    certificado, clave = tmp_path / "a.crt", tmp_path / "a.key"
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "45", "-subj", "/CN=argonavis.prueba",
                    "-keyout", str(clave), "-out", str(certificado)], check=True, capture_output=True, timeout=120)
    fecha = subprocess.run([openssl, "x509", "-noout", "-enddate", "-in", str(certificado)], check=True,
                           capture_output=True, text=True).stdout.strip().removeprefix("notAfter=")
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(certificado, clave)
    servidor = HTTPServer(("127.0.0.1", 0), _Salud)
    servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield servidor.server_port, datetime.strptime(fecha, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    servidor.shutdown()
    servidor.server_close()


def test_mira_el_certificado_que_nginx_esta_usando(servidor_https):
    """El que sirve, no el del archivo: si se cambió y nginx no lo recargó, sigue con el viejo."""
    puerto, vence = servidor_https
    sistema = vigilar.Sistema(puerto_https=puerto)
    assert sistema.vencimiento_certificado() == vence
    assert sistema.salud(https=True) == "", "por «localhost» no es el nombre del certificado: no se valida"


def test_si_https_no_contesta(servidor_https):
    sistema = vigilar.Sistema(puerto_https=1)
    with pytest.raises(OSError):
        sistema.vencimiento_certificado()
    assert "no responde" in sistema.salud(https=True)


def test_las_dos_formas_de_fecha_de_un_certificado():
    """Hasta 2049 con el año en dos cifras y, desde 2050, en cuatro."""
    corta, larga = b"\x17\x0d" + b"261122120000Z", b"\x18\x0f" + b"21560101000000Z"
    assert vigilar.vence_el(b"\x30\x82" + corta + b"\x17\x0d" + b"280103040506Z" + corta) == \
        datetime(2028, 1, 3, 4, 5, 6, tzinfo=timezone.utc)
    assert vigilar.vence_el(corta + larga) == datetime(2156, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        vigilar.vence_el(b"nada")


# ── El programa ───────────────────────────────────────────────────────────────

def test_corre_con_el_python_de_rocky_9():
    """El del sistema es 3.9: nada de sintaxis más nueva."""
    ast.parse((RAIZ / "vigilar.py").read_text(encoding="utf-8"), feature_version=(3, 9))


def test_probar_manda_un_correo_de_prueba(servidor, capsys):
    assert vigilar.probar(servidor, CONFIG, AHORA) == 0
    assert "prueba" in servidor.enviados[0]["Subject"].lower()
    assert vigilar.probar(servidor, {**CONFIG, "CORREO_ALERTAS": ""}, AHORA) == 1
    servidor.error_de_correo = smtplib.SMTPRecipientsRefused({"a@x": (550, b"5.7.54 Unable to relay")})
    assert vigilar.probar(servidor, CONFIG, AHORA) == 1
    assert "5.7.54" in capsys.readouterr().out, "dice por qué no salió"
