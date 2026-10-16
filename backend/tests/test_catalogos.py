"""Catálogos: un puesto con historial no se borra, y un choque con la BD no es un 500."""
import secrets
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.models.solicitud import Solicitud
from app.domain.models.tramite import TipoTramite
from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.infrastructure.database import SesionLocal
from conftest import crear_actor

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _finalizada_en_otro_puesto() -> int:
    """Una solicitud autorizada en un puesto y finalizada en otro. Devuelve el
    id del puesto de finalización (que no es el puesto autorizado de nadie)."""
    creador = await crear_actor("Naviera", prefijo="nav")
    sufijo = secrets.token_hex(3)
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia {sufijo}")
        autorizado = PuestoControl(nombre=f"Puesto autorizado {sufijo}")
        finalizacion = PuestoControl(nombre=f"Puesto de finalización {sufijo}")
        s.add_all([agencia, autorizado, finalizacion])
        await s.flush()
        tipo_id = (await s.execute(select(TipoTramite.id).limit(1))).scalar_one()
        s.add(Solicitud(
            agencia_id=agencia.id, agencia_nombre=agencia.nombre, creada_por_id=creador.id,
            tipo_tramite_id=tipo_id, puesto_control_id=autorizado.id, puesto_nombre=autorizado.nombre,
            titulo="Prueba", fecha_operacion=date.today(), cantidad_tripulantes=1, estado="finalized",
            enviada_en=datetime.now(timezone.utc), puesto_finalizacion_id=finalizacion.id,
            puesto_finalizacion_nombre=finalizacion.nombre,
        ))
        await s.commit()
        return finalizacion.id


async def test_no_se_borra_el_puesto_donde_se_finalizo(cliente, admin):
    puesto_id = await _finalizada_en_otro_puesto()
    r = await cliente.delete(f"/admin/puestos/{puesto_id}", headers=admin.headers)
    assert r.status_code == 409 and "desactívalo" in r.json()["detail"]


async def test_choque_con_la_bd_responde_409(cliente, admin, monkeypatch):
    """Si un servicio no valida algo que la BD rechaza, la respuesta es 409 (no 500)."""
    puesto_id = await _finalizada_en_otro_puesto()

    async def sin_uso(self, puesto_id: int) -> bool:
        return False

    monkeypatch.setattr(RepositorioCatalogo, "puesto_en_uso", sin_uso)
    r = await cliente.delete(f"/admin/puestos/{puesto_id}", headers=admin.headers)
    assert r.status_code == 409 and r.json()["detail"].startswith("No se pudo completar")
    async with SesionLocal() as s:
        assert await s.get(PuestoControl, puesto_id) is not None
