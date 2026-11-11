"""Cola de salida de los correos (correos_salida): los avisos se guardan con la
operación, salen después y, si el servidor de correo falla, se reintentan sin
perderse. Con un SMTP falso: no envía nada."""
import asyncio
import contextlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update

from app.core import email
from app.core.email import Aviso
from app.domain.models.correo import CorreoSalida, EstadoCorreo
from app.domain.repositories.correo_repository import RepositorioCorreo
from app.infrastructure import cola_correos
from app.infrastructure.cola_correos import despachar_correos, encolar_avisos
from app.infrastructure.database import SesionLocal
from app.main import aplicacion  # noqa: F401  (registra todos los modelos antes de la primera consulta)

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _aviso(numero: str, destinatarios=("agencia@prueba.local",)) -> Aviso:
    return Aviso(destinatarios=list(destinatarios), numero=numero, estado="Aprobada",
                 titulo="La autorización fue aprobada", intro="Prueba de la cola.",
                 campos=[("Buque", "ISTMO EXPRESS")], tono="verde")


def _numero() -> str:
    return f"AM-PRUEBA-{secrets.token_hex(3)}"


class SmtpFalso:
    """Registra los asuntos enviados; `fallas` cuenta cuántos envíos fallan antes de andar.
    Con `esperar_a`, cada envío espera (hasta 2 s) a que haya esos envíos en curso a la
    vez: así una prueba de despachos en paralelo no depende de la velocidad del equipo.
    Con la máquina cargada, un despacho terminaba todo antes de que arrancaran los otros
    y la prueba fallaba sin que hubiera duplicados (visto una vez, el 2026-11-10)."""
    def __init__(self, fallas: int = 0, demora: float = 0, esperar_a: int = 0):
        self.asuntos: list[str] = []
        self.fallas = fallas
        self.demora = demora
        self.a_la_vez = self.maximo_a_la_vez = 0   # envíos en curso al mismo tiempo
        self.esperar_a = esperar_a
        self.juntos = asyncio.Event()

    async def __call__(self, mensaje, **_):
        self.a_la_vez += 1
        self.maximo_a_la_vez = max(self.maximo_a_la_vez, self.a_la_vez)
        if self.a_la_vez >= self.esperar_a:
            self.juntos.set()
        try:
            if self.esperar_a:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self.juntos.wait(), timeout=2)
            await asyncio.sleep(self.demora)
        finally:
            self.a_la_vez -= 1
        if self.fallas:
            self.fallas -= 1
            raise ConnectionRefusedError("SMTP caído")
        self.asuntos.append(mensaje["Subject"])


@pytest.fixture(autouse=True)
async def cola_vacia(monkeypatch):
    """Cada prueba empieza y termina con la cola vacía y un servidor de correo configurado."""
    monkeypatch.setattr(email.configuracion, "MAIL_HOST", "smtp.prueba.local")
    async with SesionLocal() as s:
        await s.execute(delete(CorreoSalida))
        await s.commit()
    yield
    async with SesionLocal() as s:
        await s.execute(delete(CorreoSalida))
        await s.commit()


async def _encolar(*avisos: Aviso) -> None:
    async with SesionLocal() as s:
        await encolar_avisos(s, list(avisos))
        await s.commit()


async def _fila(numero: str) -> CorreoSalida:
    async with SesionLocal() as s:
        return (await s.execute(select(CorreoSalida).where(CorreoSalida.numero == numero))).scalar_one()


async def test_el_aviso_se_guarda_y_sale_despues(monkeypatch):
    smtp = SmtpFalso()
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)
    numero = _numero()
    await _encolar(_aviso(numero, destinatarios=[" agencia@prueba.local ", "agencia@prueba.local", ""]))
    assert smtp.asuntos == [], "encolar no envía"

    assert await despachar_correos() == 1
    assert smtp.asuntos == [f"Autorizaciones Marítimas · {numero} · Aprobada"]
    fila = await _fila(numero)
    assert fila.estado == EstadoCorreo.ENVIADO.value and fila.intentos == 1 and fila.enviado_en
    assert fila.aviso["destinatarios"] == ["agencia@prueba.local"], "sin espacios, vacíos ni repetidos"
    assert await despachar_correos() == 0, "lo enviado no se vuelve a enviar"


async def test_si_la_operacion_se_revierte_el_aviso_no_sale(monkeypatch):
    smtp = SmtpFalso()
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)
    async with SesionLocal() as s:
        assert await encolar_avisos(s, [_aviso(_numero())]) == 1
        await s.rollback()
    assert await despachar_correos() == 0 and smtp.asuntos == []


async def test_con_el_correo_caido_se_reintenta_con_esperas_crecientes(monkeypatch):
    monkeypatch.setattr(email.aiosmtplib, "send", SmtpFalso(fallas=2))
    numero = _numero()
    await _encolar(_aviso(numero))

    assert await despachar_correos() == 0
    fila = await _fila(numero)
    espera = (fila.proximo_intento - datetime.now(timezone.utc)).total_seconds()
    assert fila.estado == EstadoCorreo.PENDIENTE.value and fila.intentos == 1
    assert 25 < espera <= 30, "el primer reintento, a los 30 segundos"
    assert "SMTP caído" in fila.ultimo_error
    assert await despachar_correos() == 0, "antes de la hora no se reintenta"

    for intentos, siguiente in ((2, 120), (3, None)):
        async with SesionLocal() as s:   # llegó la hora del reintento
            await s.execute(update(CorreoSalida).where(CorreoSalida.numero == numero)
                            .values(proximo_intento=datetime.now(timezone.utc) - timedelta(seconds=1)))
            await s.commit()
        await despachar_correos()
        fila = await _fila(numero)
        assert fila.intentos == intentos
        if siguiente:
            espera = (fila.proximo_intento - datetime.now(timezone.utc)).total_seconds()
            assert siguiente - 5 < espera <= siguiente and fila.estado == EstadoCorreo.PENDIENTE.value
    assert fila.estado == EstadoCorreo.ENVIADO.value, "al tercer intento, con el correo de vuelta, sale"


async def test_agotados_los_reintentos_queda_fallido(monkeypatch):
    monkeypatch.setattr(email.aiosmtplib, "send", SmtpFalso(fallas=99))
    monkeypatch.setattr(cola_correos, "ESPERAS_REINTENTO", (0, 0))   # 3 intentos, sin esperar
    numero = _numero()
    await _encolar(_aviso(numero))
    for _ in range(3):   # un intento por despacho: con el correo caído, el despacho para en el primer error
        await despachar_correos()
    fila = await _fila(numero)
    assert fila.estado == EstadoCorreo.FALLIDO.value and fila.intentos == 3 and fila.enviado_en is None


async def test_con_el_correo_caido_el_despacho_no_insiste_con_toda_la_cola(monkeypatch):
    smtp = SmtpFalso(fallas=1)
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)
    primero, segundo = _numero(), _numero()
    await _encolar(_aviso(primero), _aviso(segundo))
    assert await despachar_correos() == 0
    intentos = {(await _fila(n)).intentos for n in (primero, segundo)}
    assert intentos == {0, 1}, "solo se intentó uno: los demás fallarían igual"
    assert await despachar_correos() == 1 and len(smtp.asuntos) == 1, "el que no se intentó sale en la siguiente vuelta"


async def test_un_aviso_que_no_se_puede_armar_queda_fallido_sin_reintentos(monkeypatch):
    smtp = SmtpFalso()
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)

    def armar_roto(*_):
        raise ValueError("cabecera inválida")

    monkeypatch.setattr(cola_correos, "construir_mensaje", armar_roto)
    numero = _numero()
    await _encolar(_aviso(numero))
    assert await despachar_correos() == 0
    fila = await _fila(numero)
    assert fila.estado == EstadoCorreo.FALLIDO.value and fila.intentos == 1 and "cabecera inválida" in fila.ultimo_error
    assert smtp.asuntos == []


async def test_varios_despachos_a_la_vez_no_envian_dos_veces(monkeypatch):
    """Como los workers de producción, cada uno con su despacho (_despachar_lote,
    sin el «uno a la vez» del proceso): cada correo se toma con FOR UPDATE SKIP LOCKED."""
    smtp = SmtpFalso(demora=0.05, esperar_a=2)
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)
    numeros = [_numero() for _ in range(6)]
    await _encolar(*(_aviso(n) for n in numeros))
    lotes = await asyncio.gather(*(cola_correos._despachar_lote(50) for _ in range(3)))
    assert sum(enviados for enviados, _ in lotes) == 6
    assert smtp.maximo_a_la_vez > 1, "los tres despachos enviaban a la vez"
    assert sorted(smtp.asuntos) == sorted(f"Autorizaciones Marítimas · {n} · Aprobada" for n in numeros)


async def test_en_un_proceso_hay_un_solo_despacho_a_la_vez(monkeypatch):
    """Cada respuesta que encola avisos lanza un despacho, y cada despacho retiene
    una conexión de la BD mientras espera al SMTP. En un mismo proceso, los que
    llegan mientras otro despacha le piden otra vuelta y terminan enseguida."""
    smtp = SmtpFalso(demora=0.05)
    monkeypatch.setattr(email.aiosmtplib, "send", smtp)
    numeros = [_numero() for _ in range(6)]
    await _encolar(*(_aviso(n) for n in numeros))
    enviados = await asyncio.gather(*(despachar_correos() for _ in range(3)))
    assert sorted(enviados) == [0, 0, 6], "uno despacha todo; los otros dos no toman conexiones"
    assert smtp.maximo_a_la_vez == 1
    assert len(smtp.asuntos) == 6


async def test_sin_servidor_de_correo_no_se_encola(monkeypatch):
    monkeypatch.setattr(email.configuracion, "MAIL_HOST", "")
    async with SesionLocal() as s:
        assert await encolar_avisos(s, [_aviso(_numero())]) == 0
        await s.commit()
        assert (await s.execute(select(CorreoSalida))).first() is None


async def test_se_borran_los_terminados_de_mas_de_30_dias():
    viejo = datetime.now(timezone.utc) - timedelta(days=31)
    filas = {"enviado viejo": (EstadoCorreo.ENVIADO, viejo), "fallido viejo": (EstadoCorreo.FALLIDO, viejo),
             "pendiente viejo": (EstadoCorreo.PENDIENTE, viejo),
             "enviado reciente": (EstadoCorreo.ENVIADO, datetime.now(timezone.utc))}
    async with SesionLocal() as s:
        for nombre, (estado, creado) in filas.items():
            s.add(CorreoSalida(numero=nombre[:20], asunto=nombre, aviso={}, estado=estado.value, creado_en=creado))
        await s.commit()
        assert await RepositorioCorreo(s).borrar_terminados(datetime.now(timezone.utc) - timedelta(days=30)) == 2
        await s.commit()
        quedan = sorted((await s.execute(select(CorreoSalida.asunto))).scalars())
    assert quedan == ["enviado reciente", "pendiente viejo"], "los pendientes nunca se borran"
