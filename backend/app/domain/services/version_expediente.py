"""La foto de un expediente tal como se envió, y qué cambió de una versión a otra (2026-11-22).

Al corregir una devuelta, la agencia cambia los datos, los tripulantes y los documentos. Antes
de que eso pase se guarda la foto de lo que había enviado (`solicitud_versiones`): con los
nombres y las palabras de ese día, para que se lea igual dentro de muchos años, aunque cambien
el catálogo o las columnas. Por eso va en pares (rótulo, valor) y no en los campos de la tabla."""
from datetime import date

from app.domain.models.solicitud import (
    ETIQUETA_OPERACION, DocumentoSolicitud, Solicitud, TripulanteSolicitud, texto_dias,
)
from app.domain.services.tramite_service import ETIQUETA_RANGO

FORMATO = 1
DOCUMENTO_ADICIONAL = "Documento adicional"
_VERIFICACION = "Verificación de UCVMM"   # no la cambia la agencia: no entra en la comparación
_SEXO = {"M": "Masculino", "F": "Femenino", "X": "No especificado"}

Par = list[str]   # [rótulo, valor]


def _f(valor: date | None) -> str | None:
    return valor.strftime("%d/%m/%Y") if valor else None


def _pares(*pares: tuple[str, str | None]) -> list[Par]:
    """Solo los que tienen valor."""
    return [[rotulo, valor] for rotulo, valor in pares if valor]


def _datos(s: Solicitud, bandera: str | None) -> list[Par]:
    return _pares(
        ("Trámite", s.tipo_tramite.nombre), ("Agencia naviera", s.agencia_nombre),
        ("Puesto de Control Migratorio", s.puesto_nombre), ("Cambio de puerto a", s.puesto_destino_nombre),
        ("Operación", ETIQUETA_OPERACION.get(s.operacion or "")),
        ("Días del sellado", texto_dias(s.dias_sellado) if s.dias_sellado else None),
        ("Subir y bajar", "Sí" if s.subir_y_bajar else None),
        ("Fecha de la operación", _f(s.fecha_operacion)), ("Buque", s.nombre_buque), ("IMO", s.imo), ("Bandera", bandera),
        ("Puerto", s.nombre_puerto), ("Puerto de desembarque", s.puerto_desembarque),
        ("Clínica u hospital", s.clinica_hospital), ("Motivo", s.motivo), ("Observaciones", s.observaciones),
    )


def _tripulante(t: TripulanteSolicitud) -> dict:
    verificacion = None if t.con_impedimento is None else "Con impedimento" if t.con_impedimento else "Sin impedimento"
    return {
        "id": t.id, "nombre": t.nombre_completo,
        "datos": _pares(
            ("Nacionalidad", t.nacionalidad_ref.nombre if t.nacionalidad_ref else t.nacionalidad),
            ("Fecha de nacimiento", _f(t.fecha_nacimiento)),
            ("País de nacimiento", t.pais_nacimiento_ref.nombre if t.pais_nacimiento_ref else t.pais_nacimiento),
            ("Sexo", _SEXO.get(t.sexo, t.sexo)), ("Pasaporte", t.pasaporte), ("Pasaporte vence", _f(t.pasaporte_expira)),
            ("Seamanbook", t.libreta_marino), ("Seamanbook vence", _f(t.libreta_expira)),
            ("Rango", ETIQUETA_RANGO.get(t.rango, t.rango)), ("Ocupación", t.ocupacion), (_VERIFICACION, verificacion),
        ),
    }


def _documento(d: DocumentoSolicitud, nombres: dict[int, str]) -> dict:
    return {
        "id": d.id, "documento": d.documento.nombre if d.documento else None,
        "tripulante": nombres.get(d.tripulante_id) if d.tripulante_id else None, "nombre": d.nombre_original,
    }


def foto(s: Solicitud, bandera: str | None) -> dict:
    """Lo que la solicitud tiene ahora: sus datos, sus tripulantes y sus documentos."""
    nombres = {t.id: t.nombre_completo for t in s.tripulantes}
    return {
        "formato": FORMATO,
        "datos": _datos(s, bandera),
        "tripulantes": [_tripulante(t) for t in s.tripulantes],
        "documentos": [_documento(d, nombres) for d in s.documentos],
    }


def nombre_documento(d: dict) -> str:
    dueno = f" de {d['tripulante']}" if d["tripulante"] else ""
    return f"{d['documento'] or DOCUMENTO_ADICIONAL}{dueno} ({d['nombre']})"


def _cambios(antes: list[Par], despues: list[Par], *, de: str = "") -> list[str]:
    """Los valores que cambiaron, en el orden de `antes` y, al final, los nuevos."""
    a, d = dict(antes), dict(despues)
    partes = []
    for rotulo in [*a, *(r for r in d if r not in a)]:
        if rotulo != _VERIFICACION and a.get(rotulo) != d.get(rotulo):
            nombre = f"{de}, {rotulo[0].lower()}{rotulo[1:]}" if de else rotulo
            partes.append(f"{nombre}: {a.get(rotulo, '(vacío)')} → {d.get(rotulo, '(vacío)')}")
    return partes


def comparar(antes: dict, despues: dict) -> list[str]:
    """Qué cambió la agencia de una versión a la siguiente, en palabras."""
    partes = _cambios(antes["datos"], despues["datos"])

    nuevos = {t["id"]: t for t in despues["tripulantes"]}
    for t in antes["tripulantes"]:
        otro = nuevos.get(t["id"])
        if otro is None:
            partes.append(f"Tripulante quitado: {t['nombre']}")
    for t in antes["tripulantes"]:
        otro = nuevos.get(t["id"])
        if otro is not None:
            partes += _cambios([["Nombre", t["nombre"]], *t["datos"]], [["Nombre", otro["nombre"]], *otro["datos"]], de=t["nombre"])
    viejos = {t["id"] for t in antes["tripulantes"]}
    partes += [f"Tripulante agregado: {t['nombre']}" for t in despues["tripulantes"] if t["id"] not in viejos]

    ids_antes, ids_despues = ({d["id"] for d in v["documentos"]} for v in (antes, despues))
    partes += [f"Documento retirado: {nombre_documento(d)}" for d in antes["documentos"] if d["id"] not in ids_despues]
    partes += [f"Documento agregado: {nombre_documento(d)}" for d in despues["documentos"] if d["id"] not in ids_antes]
    return partes
