"""Backend para el recorrido completo del frontend (Playwright: frontend/e2e).

Crea la BD `argonavis_e2e` en el servidor de TEST_DATABASE_URL o DATABASE_URL
(la de desarrollo no se toca), la migra y siembra una agencia, un puesto y una
cuenta local por rol. Levanta la API en 127.0.0.1:8001 sin correos ni límite de
peticiones. Si quedó la BD de una corrida interrumpida, la borra al empezar.

Lo arranca Playwright (playwright.config.ts) y, al terminar, lo vuelve a llamar
con --limpiar para borrar la BD (en Windows corta el servidor sin dejarlo cerrar).
A mano:
    cd backend
    venv\\Scripts\\python tests\\servidor_e2e.py [--limpiar]
"""
import asyncio
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from sqlalchemy.engine import make_url

from entorno_pruebas import BACKEND, alembic, servidor_bd, sql_admin, url_admin, variables

PUERTO = int(os.environ.get("E2E_PUERTO_API", "8001"))
URL_WEB = os.environ.get("E2E_URL_WEB", "http://localhost:5174")
NOMBRE_BD = "argonavis_e2e"
STORAGE = Path(tempfile.gettempdir()) / "argonavis_e2e_documentos"

# Solo existen en la BD temporal. Espejo de frontend/e2e/datos.ts.
CLAVE = "Prueba-E2e-2026!"
AGENCIA = "Agencia E2E, S.A."
PUESTO = "Puesto E2E"
# El puesto de las pruebas es del Sector Pacífico (2026-11-10): el revisor del
# Atlántico no ve sus solicitudes, y el supervisor general las ve sin decidir.
SECTOR_DEL_PUESTO = "Sector Pacífico"
# Para el cambio de puerto (2026-11-13): otro puesto del mismo sector y uno del otro.
PUESTO_MISMO_SECTOR = "Puesto E2E Rodman"
PUESTO_OTRO_SECTOR = "Puesto E2E Atlántico"
# A los tripulantes de esta nacionalidad se les pide la Visa (2026-11-14).
NACIONALIDAD_RESTRINGIDA = "CUB"
# Una solicitud del trámite de Técnico, aprobada fuera del horario con recargo, del
# Puesto E2E Rodman (2026-11-16): para la boleta de recargo y el supervisor general, que
# solo ve ese trámite. En Rodman, para que no aparezca en la bandeja del Puesto E2E.
NUMERO_RECARGO = "AM-E2E-RECARGO"
CUENTAS = [  # usuario, nombre, apellido, rol, ¿de la agencia?, ¿del puesto?, sector
    ("e2e.agencia", "Laura", "Agencia", "Naviera", True, False, None),
    ("e2e.ucvmm", "Ricardo", "Revisor", "UCVMM", False, False, "Sector Pacífico"),
    ("e2e.atlantico", "Marta", "Atlántico", "UCVMM", False, False, "Sector Atlántico"),
    ("e2e.supervisor", "Sofía", "Supervisora", "Supervisor general", False, False, None),
    # Las estadísticas, desde el 2026-11-18 (UCVMM ya no las ve).
    ("e2e.supsector", "Sergio", "Sectorial", "Supervisor de sector", False, False, "Sector Pacífico"),
    ("e2e.puesto", "Ana", "Puesto", "Puesto de Control", False, True, None),
    ("e2e.admin", "José", "Administrador", "Administrador", False, False, None),
]

# ── Entorno (antes de importar la app: la configuración se lee una sola vez) ──

_base = servidor_bd()
URL_ADMIN = url_admin(_base)
# El backend del E2E entra con su propia cuenta, con lo justo, como en producción
# (infrastructure/permisos_bd.py): si algo pide un permiso que no tiene, el recorrido falla.
URL_DUENA = f"{_base}/{NOMBRE_BD}"
ROL_APP = "argonavis_e2e_app"
URL_APP = make_url(URL_DUENA).set(username=ROL_APP, password=secrets.token_hex(16)).render_as_string(hide_password=False)

# DATABASE_URL, para migrar; el backend pasa a URL_APP (main).
os.environ.update(variables(URL_DUENA, STORAGE, APP_URL=URL_WEB, FRONTEND_URL=URL_WEB))
sys.path.insert(0, str(BACKEND))


def _sql_admin(sentencia: str) -> None:
    sql_admin(URL_ADMIN, sentencia)


def limpiar() -> None:
    _sql_admin(f'DROP DATABASE IF EXISTS "{NOMBRE_BD}" WITH (FORCE)')
    _sql_admin(f'DROP ROLE IF EXISTS "{ROL_APP}"')
    shutil.rmtree(STORAGE, ignore_errors=True)


def preparar_bd() -> None:
    limpiar()
    _sql_admin(f'CREATE DATABASE "{NOMBRE_BD}"')
    migracion = alembic("upgrade", "head")
    if migracion.returncode:
        raise SystemExit(migracion.stderr[-3000:])


async def sembrar() -> None:
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from sqlalchemy import insert, select, update

    from app.core.horario import ZONA_PANAMA
    from app.core.security import hashear_password
    from app.domain.models.catalogo import (
        AgenciaNaviera, Pais, PuestoControl, Sector, usuarios_puestos, usuarios_sectores,
    )
    from app.domain.models.rol import Rol
    from app.domain.models.solicitud import EventoSolicitud, Solicitud
    from app.domain.models.tramite import TipoTramite
    from app.domain.models.user import TipoUsuario, Usuario
    from app.infrastructure.database import SesionLocal, motor_bd

    async with SesionLocal() as s:
        sectores = {x.nombre: x.id for x in (await s.execute(select(Sector))).scalars()}
        agencia = AgenciaNaviera(nombre=AGENCIA)
        puesto = PuestoControl(nombre=PUESTO, sector_id=sectores[SECTOR_DEL_PUESTO])
        rodman = PuestoControl(nombre=PUESTO_MISMO_SECTOR, sector_id=sectores[SECTOR_DEL_PUESTO])
        s.add_all([agencia, puesto, rodman,
                   PuestoControl(nombre=PUESTO_OTRO_SECTOR, sector_id=sectores["Sector Atlántico"])])
        await s.flush()
        clave = hashear_password(CLAVE)
        ids = {}
        for usuario, nombre, apellido, rol, de_agencia, de_puesto, sector in CUENTAS:
            rol_id = (await s.execute(select(Rol.id).where(Rol.nombre == rol))).scalar_one()
            u = Usuario(username=usuario, name=nombre, last_name=apellido, user_type=TipoUsuario.LOCAL,
                        password_hash=clave, rol_id=rol_id, agencia_id=agencia.id if de_agencia else None)
            s.add(u)
            await s.flush()
            ids[usuario] = (u.id, u.full_name)
            if de_puesto:
                await s.execute(insert(usuarios_puestos).values(usuario_id=u.id, puesto_id=puesto.id))
            if sector:
                await s.execute(insert(usuarios_sectores).values(usuario_id=u.id, sector_id=sectores[sector]))
        await s.execute(update(Pais).where(Pais.codigo == NACIONALIDAD_RESTRINGIDA).values(nacionalidad_restringida=True))

        # La solicitud de Técnico aprobada el último sábado a las 16:20, con el recargo.
        tecnico = (await s.execute(select(TipoTramite.id).where(TipoTramite.codigo == "F3-TECNICO"))).scalar_one()
        sabado = datetime.now(ZONA_PANAMA).date() - timedelta(days=1)
        while sabado.weekday() != 5:
            sabado -= timedelta(days=1)
        aprobada = datetime.combine(sabado, time(16, 20), ZONA_PANAMA)
        operacion = datetime.now(ZONA_PANAMA).date() + timedelta(days=7)
        (agencia_id, agencia_nombre), (ucvmm_id, ucvmm_nombre) = ids["e2e.agencia"], ids["e2e.ucvmm"]
        solicitud = Solicitud(
            numero=NUMERO_RECARGO, agencia_id=agencia.id, agencia_nombre=AGENCIA, creada_por_id=agencia_id,
            tipo_tramite_id=tecnico, puesto_control_id=rodman.id, puesto_nombre=PUESTO_MISMO_SECTOR,
            titulo="Técnicos del MSC E2E", nombre_buque="MSC E2E", imo="9074729", fecha_operacion=operacion,
            operacion="subir_y_bajar",   # la del trámite de Técnico (2026-11-18)
            # created_at igual al envío, como en la realidad: si queda en «ahora», el tiempo de
            # respuesta de las estadísticas sale negativo (2026-11-17).
            cantidad_tripulantes=0, estado="approved", enviada_en=aprobada - timedelta(hours=3),
            created_at=aprobada - timedelta(hours=3),
            aprobada_en=aprobada, aprobada_por_id=ucvmm_id, costo_fuera_de_horario=Decimal("20.00"),
            vigente_hasta=datetime.combine(operacion, time(23, 59, 59), ZONA_PANAMA),
            codigo_verificacion=secrets.token_urlsafe(24),
        )
        s.add(solicitud)
        await s.flush()
        s.add_all([
            EventoSolicitud(solicitud_id=solicitud.id, tipo="creada", estado_nuevo="review", usuario_id=agencia_id,
                            usuario_nombre=agencia_nombre, creado_en=aprobada - timedelta(hours=3)),
            EventoSolicitud(solicitud_id=solicitud.id, tipo="aprobada", estado_anterior="review",
                            estado_nuevo="approved", usuario_id=ucvmm_id, usuario_nombre=ucvmm_nombre,
                            creado_en=aprobada),
        ])
        await s.commit()
    await motor_bd.dispose()


def main() -> None:
    if "--limpiar" in sys.argv:
        limpiar()
        return
    preparar_bd()
    from app.infrastructure.permisos_bd import aplicar
    print(aplicar(URL_DUENA, URL_APP), file=sys.stderr)   # sale en el log de Playwright
    os.environ["DATABASE_URL"] = URL_APP   # antes de importar la app: la siembra ya entra con ella
    asyncio.run(sembrar())

    import uvicorn

    from app.core.rate_limit import limiter
    from app.main import aplicacion

    limiter.enabled = False
    try:
        uvicorn.run(aplicacion, host="127.0.0.1", port=PUERTO, log_level="warning")
    finally:
        limpiar()


if __name__ == "__main__":
    main()
