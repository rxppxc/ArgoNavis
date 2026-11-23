"""Cuántas consultas a la base hace cada pedido para saber quién pide (2026-11-22, pendiente 16
de CLAUDE.md).

Antes, cada pedido leía al usuario dos veces (al revisar el token y otra vez para la ruta), cada
una con su rol y su agencia en consultas aparte, y los permisos de su rol en cada comprobación.
Ahora: una vez el usuario, con su rol y su agencia en la misma consulta, y una vez los permisos.
Si una ruta nueva vuelve a leerlos, falla aquí."""
import re
import secrets
from contextlib import contextmanager

import pytest
from sqlalchemy import event, insert

from app.domain.models.catalogo import usuarios_puestos
from app.infrastructure.database import SesionLocal, motor_bd
from ayudas import cabecera, enviar, pdf, tripulante
from conftest import crear_actor, id_sector

pytestmark = pytest.mark.asyncio(loop_scope="session")

DOCS = ("DOC-VISA-MARINO", "DOC-GENERALES-PASAPORTE", "DOC-LIBRETA-MARINO")


@contextmanager
def consultas():
    """Las sentencias que llegan a PostgreSQL mientras dura el bloque."""
    hechas: list[str] = []

    def anotar(conexion, cursor, sentencia, parametros, contexto, varias):
        hechas.append(" ".join(sentencia.split()))

    event.listen(motor_bd.sync_engine, "before_cursor_execute", anotar)
    try:
        yield hechas
    finally:
        event.remove(motor_bd.sync_engine, "before_cursor_execute", anotar)


@pytest.fixture(scope="module")
async def e(cliente, admin, sysadmin):
    sufijo = secrets.token_hex(3)
    puesto = (await cliente.post("/admin/puestos", json={"nombre": f"Puesto Consultas {sufijo}", "sector_id": await id_sector()},
                                 headers=admin.headers)).json()
    agencia = (await cliente.post("/admin/agencias", json={"nombre": f"Agencia Consultas {sufijo}"}, headers=admin.headers)).json()
    del_puesto = await crear_actor("Puesto de Control", prefijo="puesto")
    async with SesionLocal() as s:
        await s.execute(insert(usuarios_puestos).values(usuario_id=del_puesto.id, puesto_id=puesto["id"]))
        await s.commit()
    naviera = await crear_actor("Naviera", agencia_id=agencia["id"], prefijo="naviera")
    asignaciones = [{"documento_codigo": c, "indice_tripulante": 0} for c in DOCS]
    datos = cabecera("F3-EMBARQUE", puesto["id"], tripulantes=[tripulante("Ana")], asignaciones=asignaciones)
    r = await enviar(cliente, naviera, datos, [pdf(c.lower()) for c in DOCS])
    assert r.status_code == 201, r.text
    return {"naviera": naviera, "revisor": await crear_actor("UCVMM", prefijo="revisor"), "admin": admin,
            "sysadmin": sysadmin, "solicitud": r.json()["id"]}


# (quién, ruta, cuántas consultas hace en total, donde no depende de los datos). Con los datos
# de este módulo, el 2026-11-22: 1, 13, 25, 15, 27, 13 y 4 (antes, 4, 20, 28, 20, 29, 17 y 6). Las
# bandejas y el expediente cargan más o menos relaciones según las solicitudes que haya: ahí
# solo se cuenta lo de quién pide.
PEDIDOS = [
    ("naviera", "/auth/me", 1),
    ("naviera", "/solicitudes/agencia", None),
    ("naviera", "/solicitudes/{solicitud}", None),
    ("revisor", "/solicitudes/revision", None),
    ("revisor", "/solicitudes/{solicitud}", None),
    ("admin", "/solicitudes/revision", None),
    ("sysadmin", "/admin/usuarios", 4),
]


@pytest.mark.parametrize(("quien", "ruta", "tope"), PEDIDOS)
async def test_quien_pide_se_lee_una_sola_vez(cliente, e, quien, ruta, tope):
    with consultas() as hechas:
        r = await cliente.get(ruta.format(**e), headers=e[quien].headers)
    assert r.status_code == 200, r.text
    al_usuario = [s for s in hechas if re.search(r"\bFROM users\b.*\bWHERE users\.id = ", s)]
    a_los_permisos = [s for s in hechas if re.search(r"\bFROM permisos\b", s)]
    assert len(al_usuario) == 1, "el usuario, una vez (con su rol y su agencia)"
    assert len(a_los_permisos) <= 1, "los permisos de su rol, una vez"
    assert tope is None or len(hechas) <= tope, "\n".join(s[:140] for s in hechas)


async def test_los_permisos_cambiados_valen_en_el_mismo_pedido():
    """Se guardan mientras dura el pedido; si el pedido cambia los de un rol, se vuelven a leer."""
    from sqlalchemy import select

    from app.core.permisos import codigos_permiso
    from app.domain.models.rol import Permiso
    from app.domain.models.user import Usuario
    from app.domain.schemas.rol import DatosCrearRol
    from app.domain.services.rol_service import ServicioRoles

    async with SesionLocal() as sesion:
        servicio = ServicioRoles(sesion)
        rol = await servicio.crear(DatosCrearRol(nombre=f"Rol consultas {secrets.token_hex(3)}"))
        usuario = Usuario(username=f"c.{secrets.token_hex(3)}", rol_id=rol.id)
        sesion.add(usuario)
        await sesion.flush()
        assert await codigos_permiso(sesion, usuario) == set()
        permiso = (await sesion.execute(select(Permiso).where(Permiso.codigo == "T-CREAR-BASICA"))).scalar_one()
        await servicio.asignar_permisos(rol.id, [permiso.id])
        assert await codigos_permiso(sesion, usuario) == {"T-CREAR-BASICA"}
        await sesion.rollback()
