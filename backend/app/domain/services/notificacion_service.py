"""Avisos por correo de cada paso del flujo.

Arma los correos con texto plano mientras la sesión de BD sigue abierta. Van a
la cola de salida en la misma transacción y se envían después, en segundo plano
(infrastructure/cola_correos.py), para que un SMTP lento o caído no frene ni
rompa la operación, ni se pierda el aviso.

El asunto es "Autorizaciones Marítimas · {número} · {estado}" (lo arma
`Aviso`); la vista previa de la bandeja lleva el dato clave de cada paso.

Destinatarios:
  - UCVMM: el buzón CORREO_UCVMM (solicitud nueva o corregida).
  - Agencia: su buzón + sus usuarios activos (aprobada, devuelta, denegada, expirada).
    Sin unidades internas (UCVMM, sectores): la institución (2026-11-11).
  - Puesto de control: su buzón + sus funcionarios asignados (aprobada). Con
    cambio de puerto (2026-11-13), los del puesto nuevo, que es el que la finaliza.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import obtener_configuracion
from app.core.email import Aviso
from app.core.horario import aviso_fuera_de_horario, fuera_de_horario, texto_costo
from app.domain.models.solicitud import EstadoSolicitud, Solicitud
from app.domain.repositories.catalogo_repository import RepositorioCatalogo

configuracion = obtener_configuracion()
_TZ_PANAMA = ZoneInfo("America/Panama")
_LARGO_VISTA_PREVIA = 150


def _fecha_hora(valor: datetime | None) -> str:
    return valor.astimezone(_TZ_PANAMA).strftime("%d/%m/%Y a las %I:%M %p") if valor else "—"


def _fecha_hora_corta(valor: datetime | None) -> str:
    return valor.astimezone(_TZ_PANAMA).strftime("%d/%m %I:%M %p") if valor else "—"


def url_solicitud(s: Solicitud, sufijo: str = "") -> str:
    return f"{configuracion.app_base_url}/solicitudes/{s.id}{sufijo}"


def _operacion(s: Solicitud) -> str:
    return f"operación el {s.fecha_operacion.strftime('%d/%m/%Y')}"


def _puestos(s: Solicitud) -> str:
    """El puesto; con cambio de puerto (2026-11-13), los dos: «Balboa → Rodman»."""
    return f"{s.puesto_nombre} → {s.puesto_destino_nombre}" if s.puesto_destino_nombre else s.puesto_nombre


def _campos(s: Solicitud) -> list[tuple[str, str]]:
    """Datos del pase del correo (los vacíos no se muestran)."""
    return [
        ("Buque",           s.nombre_buque or ""),
        ("IMO",             s.imo or ""),
        ("Trámite",         s.tipo_tramite.nombre if s.tipo_tramite else ""),
        ("Puesto",          _puestos(s)),
        ("Operación",       s.fecha_operacion.strftime("%d/%m/%Y")),
        ("Pasajeros",       str(s.cantidad_tripulantes)),
        ("Agencia naviera", s.agencia_nombre),
    ]


def _vista_previa(*partes: str | None) -> str:
    """Lo que muestra la bandeja junto al asunto: una línea corta."""
    texto = " ".join(" · ".join(p.strip() for p in partes if p and p.strip()).split())
    return texto if len(texto) <= _LARGO_VISTA_PREVIA else texto[: _LARGO_VISTA_PREVIA - 1].rstrip() + "…"


class ServicioNotificacion:
    def __init__(self, sesion: AsyncSession):
        self.repo_catalogos = RepositorioCatalogo(sesion)

    # ── Destinatarios ────────────────────────────────────────────────────────

    async def _correos_agencia(self, s: Solicitud) -> list[str]:
        correos = [s.agencia.correo] if s.agencia and s.agencia.correo else []
        correos += await self.repo_catalogos.correos_de_agencia(s.agencia_id)
        return list(dict.fromkeys(correos))

    async def _correos_puesto(self, s: Solicitud) -> list[str]:
        """Los del puesto que la finaliza: con cambio de puerto, el nuevo."""
        puesto = s.puesto_autorizado
        correos = [puesto.correo] if puesto and puesto.correo else []
        correos += await self.repo_catalogos.correos_de_puesto(s.puesto_autorizado_id)
        return list(dict.fromkeys(correos))

    async def _correos_ucvmm(self, s: Solicitud) -> list[str]:
        """El buzón del sector del puesto (2026-11-10); sin él, el general de UCVMM."""
        correo = await self.repo_catalogos.correo_sector_de_puesto(s.puesto_control_id) or configuracion.CORREO_UCVMM
        return [correo] if correo else []

    # ── Avisos por paso ──────────────────────────────────────────────────────

    async def recibida(self, s: Solicitud, *, corregida: bool) -> list[Aviso]:
        """Solicitud nueva o corregida: a la cola de UCVMM de su sector."""
        tramite = s.tipo_tramite.nombre if s.tipo_tramite else "autorización"
        if corregida:
            estado = "Corregida"
            titulo = "Solicitud corregida por la agencia"
            intro  = f"{s.agencia_nombre} corrigió la solicitud devuelta y está de nuevo en la cola de revisión."
            previa = _vista_previa(f"{s.agencia_nombre} corrigió la solicitud", tramite, _operacion(s))
        else:
            estado = "Nueva solicitud"
            titulo = "Nueva solicitud de autorización"
            intro  = f"{s.agencia_nombre} envió una solicitud de {tramite} para revisión."
            previa = _vista_previa(s.agencia_nombre, tramite, _operacion(s))
        return self._con_destinatarios([Aviso(
            destinatarios=await self._correos_ucvmm(s), numero=s.numero or "", estado=estado,
            titulo=titulo, intro=intro, vista_previa=previa, campos=_campos(s), tono="azul",
            boton_texto="Revisar solicitud", boton_url=url_solicitud(s),
        )])

    async def aprobada(self, s: Solicitud) -> list[Aviso]:
        """A la agencia (con la autorización) y al puesto de control que la finaliza."""
        vigencia = f"Vigente hasta el {_fecha_hora(s.vigente_hasta)}."
        # Aprobada fuera del horario: el aviso y el costo migratorio (2026-11-11),
        # a la agencia y al puesto que la recibe.
        fuera = s.aprobada_en is not None and fuera_de_horario(s.aprobada_en)
        horario = "\n".join(aviso_fuera_de_horario(s.costo_fuera_de_horario)) if fuera else None
        # Solo en los trámites cuyo proceso lo indica (Desembarque, Urgencias,
        # Renovación y Shore Pass): los demás no mencionan la custodia.
        restringidos = (
            [t.nombre_completo for t in s.tripulantes if t.nacionalidad_restringida]
            if s.tipo_tramite and s.tipo_tramite.aviso_custodia else []
        )
        cambio = (f"Cambio de puerto: de {s.puesto_nombre} a {s.puesto_destino_nombre}."
                  if s.puesto_destino_nombre else None)
        # La observación de aprobación es interna de UCVMM: no va a la agencia.
        nota_agencia = "\n".join(filter(None, [
            vigencia,
            horario,
            cambio,
            f"Vale solo para {s.puesto_autorizado_nombre}: si la operación se realiza en otro puesto, "
            "la agencia debe presentar una nueva solicitud.",
            ("Nacionalidad restringida: la agencia debe realizar el trámite de solicitud de custodia para "
             + ", ".join(restringidos) + ".")
            if restringidos else None,
        ]))
        previa = _vista_previa(
            s.puesto_autorizado_nombre, _operacion(s), f"vigente hasta el {_fecha_hora_corta(s.vigente_hasta)}",
            (f"costo migratorio de {texto_costo(s.costo_fuera_de_horario)} (fuera del horario)"
             if s.costo_fuera_de_horario else "fuera del horario laboral") if fuera else None,
        )
        return self._con_destinatarios([
            Aviso(
                destinatarios=await self._correos_agencia(s), numero=s.numero or "", estado="Aprobada",
                titulo="La autorización fue aprobada",
                intro="Descarga la autorización en PDF (verificable con código QR) desde el sistema.",
                vista_previa=previa, campos=_campos(s), destacado=nota_agencia, tono="verde",
                boton_texto="Ver y descargar la autorización", boton_url=url_solicitud(s),
            ),
            Aviso(
                destinatarios=await self._correos_puesto(s), numero=s.numero or "", estado="Aprobada",
                titulo="Autorización aprobada para tu puesto de control",
                intro=(
                    "UCVMM aprobó una autorización marítima que se realizará en tu puesto de control. "
                    "Ingresa al sistema para registrar la operación y finalizarla."
                ),
                vista_previa=previa, campos=_campos(s),
                destacado="\n".join(filter(None, [vigencia, horario, cambio])),
                tono="verde", boton_texto="Abrir autorización", boton_url=url_solicitud(s),
            ),
        ])

    async def devuelta(self, s: Solicitud) -> list[Aviso]:
        return self._con_destinatarios([Aviso(
            destinatarios=await self._correos_agencia(s), numero=s.numero or "", estado="Devuelta a corrección",
            titulo="La solicitud necesita correcciones",
            intro="El Servicio Nacional de Migración revisó la solicitud y necesita que se corrija lo siguiente antes de aprobarla.",
            vista_previa=_vista_previa(f"Motivo: {s.motivo_devolucion}",
                                       f"corrige antes del {_fecha_hora_corta(s.plazo_correccion)}"),
            campos=_campos(s),
            destacado=(
                f"Motivo: {s.motivo_devolucion}\n\n"
                f"Plazo para corregir: hasta el {_fecha_hora(s.plazo_correccion)}."
            ),
            tono="naranja",
            boton_texto="Corregir solicitud", boton_url=url_solicitud(s, "/corregir"),
        )])

    async def negada(self, s: Solicitud) -> list[Aviso]:
        return self._con_destinatarios([Aviso(
            destinatarios=await self._correos_agencia(s), numero=s.numero or "", estado="Denegada",
            titulo="La solicitud fue denegada",
            intro="El Servicio Nacional de Migración revisó la solicitud de autorización y no fue aprobada.",
            vista_previa=_vista_previa(f"Motivo: {s.motivo_negacion}"),
            campos=_campos(s), destacado=f"Motivo: {s.motivo_negacion}", tono="rojo",
            boton_texto="Ver solicitud", boton_url=url_solicitud(s),
        )])

    async def expirada(self, s: Solicitud, estado_anterior: str, motivo: str) -> list[Aviso]:
        titulo = (
            "La autorización expiró sin finalizarse" if estado_anterior == EstadoSolicitud.APROBADA.value
            else "La solicitud expiró sin corregirse"
        )
        return self._con_destinatarios([Aviso(
            destinatarios=await self._correos_agencia(s), numero=s.numero or "", estado="Expirada",
            titulo=titulo,
            intro="El plazo de la solicitud venció y quedó registrada como expirada.",
            vista_previa=_vista_previa(motivo),
            campos=_campos(s), destacado=motivo, tono="gris",
            boton_texto="Ver solicitud", boton_url=url_solicitud(s),
        )])

    @staticmethod
    def _con_destinatarios(avisos: list[Aviso]) -> list[Aviso]:
        return [a for a in avisos if a.destinatarios]
