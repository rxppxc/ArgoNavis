"""Reglas puras (sin BD): IMO, política de contraseñas y checklist."""
import pytest

from app.domain.models.tramite import DocumentoRequerido, TipoTramite, TramiteDocumento
from app.domain.schemas.user import problema_de_contrasena, validar_politica_contrasena
from app.domain.services.tramite_service import ServicioTramite, TripulanteChecklist, normalizar_imo


@pytest.mark.parametrize("valor, esperado", [
    ("IMO 9074729", "9074729"),
    ("9074729", "9074729"),
    ("imo9074729", "9074729"),
    ("1234568", None),        # dígito verificador incorrecto
    ("907472", None),         # 6 dígitos
    ("IMO 90747290", None),   # 8 dígitos
    ("", None),
])
def test_normalizar_imo(valor, esperado):
    assert normalizar_imo(valor) == esperado


@pytest.mark.parametrize("clave, valida", [
    ("Ab1!x", False),                  # corta
    ("Puerto2026Balboa", False),       # la de antes: sin carácter especial
    ("puerto-2026-balboa", False),     # sin mayúscula
    ("PUERTO-2026-BALBOA", False),     # sin minúscula
    ("Puerto-Sin-Balboa", False),      # sin número
    ("Mi-Password-2026", False),       # palabra obvia
    ("Argo-Navis-2026!", False),
    ("Panamá-Puerto-2026", False),     # también con tilde
    ("Aa1!" + "x" * 61, False),        # 65: demasiado larga
    ("Puerto-2026-Balboa", True),
    ("Ñandú.Balboa-26", True),
])
def test_politica_contrasena(clave, valida):
    if valida:
        assert validar_politica_contrasena(clave) == clave
    else:
        with pytest.raises(ValueError):
            validar_politica_contrasena(clave)


def test_contrasena_sin_el_nombre_de_usuario():
    assert problema_de_contrasena("Agencia.Uno-2026", "agencia.uno") == \
        "La contraseña no puede contener el nombre de usuario."
    assert problema_de_contrasena("Puerto-2026-Balboa", "agencia.uno") is None


def test_la_temporal_cumple_la_politica():
    from app.core.security import generar_contrasena_temporal

    assert all(problema_de_contrasena(generar_contrasena_temporal()) is None for _ in range(200))


def _tipo(*filas: tuple[str, str, str, bool]) -> TipoTramite:
    """Trámite en memoria: (codigo_documento, alcance, condicion, requiere_libreta)."""
    tipo = TipoTramite(codigo="T", nombre="Trámite", formulario="formulario_3")
    for orden, (codigo, alcance, condicion, libreta) in enumerate(filas, start=1):
        documento = DocumentoRequerido(id=orden, codigo=codigo, nombre=codigo, requiere_libreta=libreta)
        tipo.documentos.append(TramiteDocumento(
            documento_id=orden, documento=documento, alcance=alcance, condicion=condicion, orden=orden,
        ))
    return tipo


def test_checklist_condiciones():
    tipo = _tipo(
        ("LISTA", "solicitud", "siempre", False),
        ("PASAPORTE", "marino", "siempre", False),
        ("LIBRETA", "marino", "solo_panamenos", True),
        ("CUSTODIA", "marino", "nacionalidad_restringida", False),
        ("CUSTODIA-GLOBAL", "solicitud", "nacionalidad_restringida", False),
    )
    tripulantes = [
        TripulanteChecklist(nombre="Panameño marino", es_panameno=True, porta_libreta=True),
        TripulanteChecklist(nombre="Panameño técnico", es_panameno=True, porta_libreta=False),
        TripulanteChecklist(nombre="Cubano", nacionalidad_restringida=True),
    ]
    casillas = ServicioTramite().construir_casillas(tipo, tripulantes)
    pares = {(c.codigo_documento, c.indice_tripulante) for c in casillas}
    assert pares == {
        ("LISTA", None),
        ("PASAPORTE", 0), ("PASAPORTE", 1), ("PASAPORTE", 2),
        ("LIBRETA", 0),                      # el técnico no porta seamanbook
        ("CUSTODIA", 2),                     # solo el restringido
        ("CUSTODIA-GLOBAL", None),           # hay al menos un restringido
    }


def test_checklist_sin_restringidos_no_pide_custodia():
    tipo = _tipo(("CUSTODIA-GLOBAL", "solicitud", "nacionalidad_restringida", False))
    resultado = ServicioTramite().evaluar(tipo, [TripulanteChecklist(nombre="Ana")], set())
    assert resultado.completo and resultado.requeridas == []


def test_checklist_describe_faltantes():
    tipo = _tipo(("PASAPORTE", "marino", "siempre", False))
    resultado = ServicioTramite().evaluar(tipo, [TripulanteChecklist(nombre="Ana Pérez")], set())
    assert not resultado.completo
    assert resultado.describir_faltantes() == "PASAPORTE de Ana Pérez"


# ── Ficha del tripulante: edad y fechas ──────────────────────────────────────

def _ficha(**cambios):
    from datetime import date
    from app.domain.schemas.solicitud import DatosTripulanteEntrada
    datos = dict(nombre="Ana", apellido="Pérez", fecha_nacimiento=date(1990, 5, 1), pais_nacimiento="PHL",
                 nacionalidad="PHL", sexo="F", pasaporte="P123456", pasaporte_expira=date(2030, 1, 1),
                 libreta_marino="SB1", libreta_expira=date(2030, 1, 1), rango="marino", ocupacion="Marinera")
    datos.update(cambios)
    return DatosTripulanteEntrada(**datos)


def _errores(ficha, hoy=None):
    from datetime import date
    hoy = hoy or date(2026, 10, 14)
    return ServicioTramite().validar_tripulantes(
        _tipo(), [ficha], fecha_referencia=hoy, hoy=hoy, codigos_pais_validos={"PHL"},
    )


@pytest.mark.parametrize("nacimiento, mayor", [
    ("2008-10-14", True),    # cumple 18 justo hoy
    ("2008-10-15", False),   # le falta un día
    ("2010-01-01", False),
    ("1990-05-01", True),
])
def test_mayoria_de_edad(nacimiento, mayor):
    from datetime import date
    errores = _errores(_ficha(fecha_nacimiento=date.fromisoformat(nacimiento)))
    assert (not any("mayor de edad" in e for e in errores)) == mayor, errores


def test_fechas_coherentes():
    from datetime import date
    assert any("no es válida" in e for e in _errores(_ficha(fecha_nacimiento=date(1899, 12, 31))))
    errores = _errores(_ficha(fecha_nacimiento=date(1990, 5, 1), pasaporte_expira=date(1990, 1, 1),
                              libreta_expira=date(1989, 1, 1)))
    assert any("pasaporte debe ser posterior" in e for e in errores)
    assert any("seamanbook debe ser posterior" in e for e in errores)
    assert _errores(_ficha()) == []
