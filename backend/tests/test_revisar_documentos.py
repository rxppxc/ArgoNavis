"""¿Siguen en el disco los documentos del expediente? (2026-11-22). Las solicitudes se
consultan años después, y un respaldo dura 14 días: un archivo que se pierde sin que nadie
lo note ya no se recupera. Lo corre verificar-despliegue.sh, cada mañana con vigilar.py."""
import hashlib
import os
import secrets
import subprocess
import sys
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.domain.models.catalogo import AgenciaNaviera, PuestoControl
from app.domain.models.solicitud import DocumentoEmitido, DocumentoSolicitud, Solicitud
from app.domain.models.tramite import TipoTramite
from app.infrastructure import almacenamiento, revisar_documentos
from app.infrastructure.database import SesionLocal
from app.infrastructure.revisar_documentos import Revision, revisar
from conftest import BACKEND, crear_actor, id_sector

asincrona = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def solicitud(cliente):
    """Una solicitud con tres documentos en el disco. Al terminar se borra."""
    sufijo = secrets.token_hex(3)
    async with SesionLocal() as s:
        agencia = AgenciaNaviera(nombre=f"Agencia Discos {sufijo}")
        puesto = PuestoControl(nombre=f"Puesto Discos {sufijo}", sector_id=await id_sector())
        s.add_all([agencia, puesto])
        await s.commit()
        tipo = (await s.execute(select(TipoTramite.id).limit(1))).scalar_one()
    naviera = await crear_actor("Naviera", agencia_id=agencia.id, prefijo="naviera")
    async with SesionLocal() as s:
        solicitud = Solicitud(
            numero=f"DD-{sufijo}", agencia_id=agencia.id, agencia_nombre=agencia.nombre, creada_por_id=naviera.id,
            tipo_tramite_id=tipo, puesto_control_id=puesto.id, puesto_nombre=puesto.nombre, titulo="Discos",
            fecha_operacion=date.today(), cantidad_tripulantes=0, enviada_en=datetime.now(timezone.utc),
        )
        s.add(solicitud)
        await s.flush()
        carpeta = almacenamiento.carpeta_solicitud(solicitud.id)
        carpeta.mkdir(parents=True, exist_ok=True)
        documentos = []
        for nombre in ("a.pdf", "b.pdf", "c.pdf"):
            (carpeta / nombre).write_bytes(b"%PDF-1.4 " + nombre.encode())
            documentos.append(DocumentoSolicitud(
                solicitud_id=solicitud.id, nombre_original="Pasaporte de Juan.pdf", nombre_almacenado=nombre,
                ruta=f"solicitud-{solicitud.id}/{nombre}", tipo_mime="application/pdf", tamano=14,
            ))
        s.add_all(documentos)
        await s.commit()
        ids = [d.id for d in documentos]
    yield {"numero": f"DD-{sufijo}", "id": solicitud.id, "carpeta": carpeta, "documentos": ids}
    async with SesionLocal() as s:
        await s.execute(delete(Solicitud).where(Solicitud.id == solicitud.id))
        await s.commit()


async def _de(solicitud: dict) -> list[str]:
    """Los problemas de esta solicitud (en la base hay documentos de otras pruebas)."""
    return [p for p in (await revisar()).problemas if solicitud["numero"] in p]


@asincrona
async def test_con_todo_en_su_lugar_no_dice_nada(solicitud):
    revision = await revisar()
    assert revision.total >= 3 and await _de(solicitud) == []


@asincrona
async def test_dice_cual_falta_o_no_mide_lo_que_debe(solicitud, monkeypatch):
    monkeypatch.setattr(revisar_documentos, "LOTE", 2)   # en varias vueltas
    (solicitud["carpeta"] / "a.pdf").unlink()
    (solicitud["carpeta"] / "c.pdf").write_bytes(b"%PDF")   # quedó a medias
    a, _, c = solicitud["documentos"]
    assert await _de(solicitud) == [
        f"{solicitud['numero']}: falta solicitud-{solicitud['id']}/a.pdf (documento {a})",
        f"{solicitud['numero']}: solicitud-{solicitud['id']}/c.pdf mide 4 bytes y debía medir 14 (documento {c})",
    ]


@asincrona
@pytest.mark.parametrize("como", ["absoluta", "con puntos"])
async def test_una_ruta_fuera_de_la_carpeta_no_se_mira(solicitud, tmp_path, como):
    ajeno = tmp_path / "ajeno.pdf"
    ajeno.write_bytes(b"x" * 14)
    fuera = str(ajeno) if como == "absoluta" else os.path.relpath(ajeno, almacenamiento.raiz_documentos()).replace("\\", "/")
    async with SesionLocal() as s:
        (await s.get(DocumentoSolicitud, solicitud["documentos"][0])).ruta = fuera
        await s.commit()
    [problema] = await _de(solicitud)
    assert "falta" in problema


@asincrona
async def test_uno_que_sale_mientras_se_revisa_no_es_un_problema(solicitud, monkeypatch):
    """Entre leer la lista y mirar el disco, uno puede dejar de estar en los dos lados."""
    original = revisar_documentos._mirar

    def mirar_y_borrar(archivos, dia):
        (solicitud["carpeta"] / "b.pdf").unlink(missing_ok=True)
        return original(archivos, dia)

    async def reemplazado(modelo, ids):
        async with SesionLocal() as s:
            await s.execute(delete(DocumentoSolicitud).where(DocumentoSolicitud.id == solicitud["documentos"][1]))
            await s.commit()
        return await registrados(modelo, ids)

    registrados = revisar_documentos._registrados
    monkeypatch.setattr(revisar_documentos, "_mirar", mirar_y_borrar)
    monkeypatch.setattr(revisar_documentos, "_registrados", reemplazado)
    assert await _de(solicitud) == []


@asincrona
async def test_tambien_los_retirados_y_las_autorizaciones_emitidas(solicitud):
    async with SesionLocal() as s:
        (await s.get(DocumentoSolicitud, solicitud["documentos"][0])).retirado_en = datetime.now(timezone.utc)
        emitida = DocumentoEmitido(solicitud_id=solicitud["id"], tipo="aprobada", ruta=f"solicitud-{solicitud['id']}/aut.pdf",
                                   tamano=4, sha256="0" * 64)
        s.add(emitida)
        await s.commit()
    (solicitud["carpeta"] / "a.pdf").unlink()
    assert await _de(solicitud) == [
        f"{solicitud['numero']}: falta solicitud-{solicitud['id']}/a.pdf (documento {solicitud['documentos'][0]})",
        f"{solicitud['numero']}: falta solicitud-{solicitud['id']}/aut.pdf (autorización emitida {emitida.id})",
    ]


@asincrona
async def test_en_un_mes_se_comprueban_todas_las_huellas(solicitud, monkeypatch):
    """Uno que mide lo mismo y cambió por dentro solo lo dice su huella, el día que le toca."""
    a, b, c = solicitud["documentos"]
    async with SesionLocal() as s:
        for i, nombre in ((a, "a.pdf"), (b, "b.pdf")):   # el tercero es de antes: sin huella
            (await s.get(DocumentoSolicitud, i)).sha256 = hashlib.sha256(b"%PDF-1.4 " + nombre.encode()).hexdigest()
        await s.commit()
    (solicitud["carpeta"] / "a.pdf").write_bytes(b"%PDF-1.4 A.pdf")
    leidos = []
    original = almacenamiento.huella_de
    monkeypatch.setattr(almacenamiento, "huella_de", lambda ruta: (leidos.append(ruta.name), original(ruta))[1])
    avisos = {}
    for dia in range(1, revisar_documentos.DIAS + 1):
        leidos.clear()
        revision = await revisar(dia)
        propios = [p for p in revision.problemas if solicitud["numero"] in p]
        if propios:
            avisos[dia] = propios
        assert revision.releidos >= len(leidos) - len(propios), "se cuentan los que se releen"
    assert len(avisos) == 1, "una vez al mes"
    [(dia, [aviso])] = avisos.items()
    assert a % revisar_documentos.DIAS == dia % revisar_documentos.DIAS
    assert aviso == (f"{solicitud['numero']}: solicitud-{solicitud['id']}/a.pdf no es el original: no coincide con su "
                     f"huella (documento {a})")


def test_el_resumen_nombra_los_primeros():
    assert Revision(total=0).resumen() == "Sin archivos registrados todavía"
    assert Revision(total=1).resumen() == "1 archivo registrado, en el disco y con su tamaño"
    assert Revision(total=1200, releidos=40).resumen() == (
        "1,200 archivos registrados, todos en el disco y con su tamaño; hoy se releyeron 40 y son los originales")
    resumen = Revision(total=40, problemas=[f"AM-{i}: falta x" for i in range(12)]).resumen()
    assert resumen.splitlines()[0] == "12 de 40 archivos no están como deben. Recupéralos del último respaldo (README → Respaldos):"
    assert "AM-9: falta x" in resumen and "AM-10: falta x" not in resumen and resumen.splitlines()[-1].strip() == "y 2 más"


@asincrona
async def test_como_lo_corre_el_servidor(solicitud):
    """En un proceso aparte: 0 si todo está, 1 si algo falta, y sin el nombre original del archivo
    (trae datos personales). No carga la aplicación entera."""
    def correr() -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "app.infrastructure.revisar_documentos"], cwd=BACKEND,
                              env={**os.environ, "PYTHONUTF8": "1"}, capture_output=True, encoding="utf-8", timeout=120)

    (solicitud["carpeta"] / "a.pdf").unlink()
    r = correr()
    assert r.returncode == 1, r.stderr
    assert f"{solicitud['numero']}: falta solicitud-{solicitud['id']}/a.pdf" in r.stdout and "Juan" not in r.stdout
    (solicitud["carpeta"] / "a.pdf").write_bytes(b"%PDF-1.4 a.pdf")
    assert solicitud["numero"] not in correr().stdout


def test_la_revision_del_despliegue_lo_corre():
    """Y con ella, vigilar.py cada mañana y la integración continua."""
    guion = (BACKEND.parent / "verificar-despliegue.sh").read_text(encoding="utf-8")
    orden = guion.index("if documentos=$(docker exec argonavis_backend python -m app.infrastructure.revisar_documentos")
    assert orden < guion.index('if [ -n "$SOLO_LA_PILA" ]; then resultado; fi'), "también con --solo-la-pila"
