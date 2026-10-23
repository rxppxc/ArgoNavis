"""Reglas espejadas en el frontend.

Los casos de backend/tests/espejo/*.json corren aquí y en las pruebas del
frontend (Vitest, `npm test`): si una regla cambia de un solo lado, falla una
de las dos. Además se comparan las constantes con las de los archivos .ts.
No usa la BD.
"""
import json
import re
from datetime import date
from pathlib import Path

import pytest

import app.main  # noqa: F401  registra todos los modelos (las relaciones se resuelven por nombre)
from app.domain.models.tramite import DocumentoRequerido, TipoTramite, TramiteDocumento
from app.domain.schemas.solicitud import DatosTripulanteEntrada
from app.domain.schemas.user import problema_de_contrasena
from app.domain.services.tramite_service import ServicioTramite, TripulanteChecklist, normalizar_imo

ESPEJO = Path(__file__).parent / "espejo"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _casos(nombre: str):
    return json.loads((ESPEJO / nombre).read_text(encoding="utf-8"))


def _ids(casos: list[dict]) -> list[str]:
    return [c["caso"] for c in casos]


# ── IMO y contraseñas ────────────────────────────────────────────────────────

IMO = _casos("imo.json")


@pytest.mark.parametrize("caso", IMO, ids=_ids(IMO))
def test_imo(caso):
    assert normalizar_imo(caso["valor"]) == caso["esperado"]


CONTRASENAS = _casos("contrasenas.json")


@pytest.mark.parametrize("caso", CONTRASENAS, ids=_ids(CONTRASENAS))
def test_contrasena(caso):
    assert problema_de_contrasena(caso["clave"], caso["usuario"]) == caso["problema"]


# ── Checklist ────────────────────────────────────────────────────────────────

CHECKLIST = _casos("checklist.json")


@pytest.mark.parametrize("caso", CHECKLIST, ids=_ids(CHECKLIST))
def test_checklist(caso):
    tipo = TipoTramite(codigo="T", nombre="Trámite", formulario="formulario_3")
    for i, d in enumerate(caso["documentos"], start=1):
        documento = DocumentoRequerido(id=i, codigo=d["codigo"], nombre=d["codigo"], requiere_libreta=d["requiere_libreta"])
        tipo.documentos.append(TramiteDocumento(
            documento_id=i, documento=documento, alcance=d["alcance"], condicion=d["condicion"], orden=d["orden"],
        ))
    tripulantes = [
        TripulanteChecklist(nombre=t["nombre"], es_panameno=t["es_panameno"], porta_libreta=t["porta_libreta"],
                            nacionalidad_restringida=t["restringida"])
        for t in caso["tripulantes"]
    ]
    casillas = ServicioTramite().construir_casillas(tipo, tripulantes)
    assert [[c.codigo_documento, c.indice_tripulante] for c in casillas] == caso["esperado"]


# ── Ficha del tripulante ─────────────────────────────────────────────────────

TRIPULANTES = _casos("tripulantes.json")

# Cada mensaje del backend, a la clave de su regla (el frontend tiene su propia tabla).
REGLAS = {
    "menor_de_edad": "debe ser mayor de edad",
    "nacimiento_invalido": "la fecha de nacimiento no es válida",
    "nacimiento_futuro": "la fecha de nacimiento debe ser anterior a hoy",
    "pasaporte_antes_de_nacer": "vencimiento del pasaporte debe ser posterior",
    "seamanbook_antes_de_nacer": "vencimiento del seamanbook debe ser posterior",
    "pasaporte_vencido": "el pasaporte vence el",
    "seamanbook_vencido": "el seamanbook vence el",
    "rango_no_permitido": "el rango debe ser",
    "marino_sin_seamanbook": "requiere el número de seamanbook",
    "pasaporte_repetido": "ya está en el tripulante",
}


def _regla(mensaje: str) -> str:
    claves = [clave for clave, texto in REGLAS.items() if texto in mensaje]
    assert len(claves) == 1, f"Mensaje sin una única regla: {mensaje}"
    return claves[0]


@pytest.mark.parametrize("caso", TRIPULANTES["casos"], ids=_ids(TRIPULANTES["casos"]))
def test_ficha_del_tripulante(caso):
    hoy = date.fromisoformat(caso["hoy"])
    operacion = date.fromisoformat(caso["fecha_operacion"])
    tipo = TipoTramite(codigo="T", nombre="Trámite", formulario="formulario_3",
                       valida_vigencia=caso["tramite"]["valida_vigencia"],
                       rangos_permitidos=caso["tramite"]["rangos_permitidos"])
    fichas = [DatosTripulanteEntrada(**{**TRIPULANTES["base"], **cambios}) for cambios in caso["tripulantes"]]
    errores = ServicioTramite().validar_tripulantes(
        tipo, fichas, fecha_referencia=max(hoy, operacion), hoy=hoy, codigos_pais_validos=set(TRIPULANTES["paises"]),
    )
    assert sorted(_regla(e) for e in errores) == sorted(caso["esperado"]), errores


# ── Constantes ───────────────────────────────────────────────────────────────

def _constante_ts(archivo: str, nombre: str):
    """Valor de `export const NOMBRE = ...;` (o sin export) de un archivo del frontend."""
    texto = (FRONTEND / archivo).read_text(encoding="utf-8")
    coincidencia = re.search(rf"\bconst {nombre}\b(?:\s*:[^=]+)?\s*=\s*(.+?);", texto, re.S)
    assert coincidencia, f"No encontré {nombre} en {archivo}"
    return json.loads(coincidencia.group(1).replace("'", '"'))


def test_constantes_iguales_en_el_frontend():
    from app.core.config import Configuracion
    from app.domain.models.solicitud import RANGOS_CON_LIBRETA
    from app.domain.schemas import user
    from app.domain.services import solicitud_service, tramite_service
    from app.infrastructure import almacenamiento

    assert set(_constante_ts("utils/archivos.ts", "EXTENSIONES_PERMITIDAS")) == almacenamiento.EXTENSIONES_PERMITIDAS
    assert _constante_ts("utils/archivos.ts", "TAMANO_MAX_MB") == almacenamiento.TAMANO_MAXIMO_MB
    assert _constante_ts("utils/contrasena.ts", "LARGO_MINIMO_CONTRASENA") == user.LARGO_MINIMO_CONTRASENA
    assert _constante_ts("utils/contrasena.ts", "LARGO_MAXIMO_CONTRASENA") == user.LARGO_MAXIMO_CONTRASENA
    assert tuple(_constante_ts("utils/contrasena.ts", "PALABRAS_PROHIBIDAS")) == user._PALABRAS_PROHIBIDAS
    assert _constante_ts("modulos/solicitudes/validacionFormulario.ts", "EDAD_MINIMA") == tramite_service.EDAD_MINIMA
    assert date.fromisoformat(_constante_ts("modulos/solicitudes/validacionFormulario.ts", "NACIMIENTO_MINIMO")) \
        == tramite_service.NACIMIENTO_MINIMO
    assert _constante_ts("modulos/solicitudes/validacionFormulario.ts", "DIAS_MAXIMOS_ANTICIPACION") \
        == Configuracion.model_fields["DIAS_MAXIMOS_ANTICIPACION"].default
    assert _constante_ts("modulos/solicitudes/DocumentosAdicionales.tsx", "MAX_ADICIONALES") \
        == solicitud_service.MAX_DOCUMENTOS_ADICIONALES
    assert set(_constante_ts("modulos/solicitudes/presentacion.ts", "RANGOS_CON_LIBRETA")) == RANGOS_CON_LIBRETA
