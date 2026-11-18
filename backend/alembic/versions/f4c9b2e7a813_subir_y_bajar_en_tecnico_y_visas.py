"""«Subir y bajar» solo en el trámite de Técnico y la visa de los restringidos según el trámite

Revision ID: f4c9b2e7a813
Revises: d2a7c5e9f831
Create Date: 2026-11-18

Pedido del usuario (2026-11-18):

  - «Subir y bajar» va solo en el trámite de Técnico, Superintendente o Supernumerario,
    como una de sus operaciones. Embarque y Desembarque dejan de preguntarlo
    (`permite_subir_y_bajar`) y de pedir la Carta de Responsabilidad (Form. No. 7) de
    cada tripulante; el trámite de Técnico la pide con la operación «Subir y bajar»
    (condición `subir_y_bajar`).
  - La «Visa» de los restringidos (DOC-VISA, en todos los trámites desde el 2026-11-14)
    queda en el trámite de Técnico, a cualquiera de sus rangos, y en los demás solo al
    Militar («se mantiene como está»). Shore Pass, que admite solo al Marino, la pierde.
  - Al Marino y al Pasajero de nacionalidad restringida de los demás trámites se les
    exige la Visa Especial de Marino (DOC-VISA-MARINO). En Embarque y Cambio de nave ya
    se le pide a todo extranjero (`solo_extranjeros`), que incluye a los restringidos.

Las solicitudes ya enviadas conservan su foto del checklist; una devuelta se corrige con
las reglas nuevas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f4c9b2e7a813'
down_revision: Union[str, None] = 'd2a7c5e9f831'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TECNICO, SHORE_PASS = 'F3-TECNICO', 'F3-SHORE-PASS'
EMBARQUE_DESEMBARQUE = ['F3-EMBARQUE', 'F3-DESEMBARQUE']
CARTA, VISA, VISA_MARINO = 'DOC-FORM7-RESPONSABILIDAD', 'DOC-VISA', 'DOC-VISA-MARINO'
RANGOS = postgresql.ARRAY(sa.String(length=20))
CODIGOS = postgresql.ARRAY(sa.String(length=50))

# Las filas de un documento con una condición, en los trámites dados (o en todos menos esos).
_FILAS = """
    documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = :documento)
    AND condicion = :condicion
    AND tipo_tramite_id IN (SELECT id FROM tipos_tramite WHERE (codigo = ANY(:codigos)) = :dentro)"""


def _parametros(documento: str, condicion: str, codigos: list[str], dentro: bool = True) -> list:
    return [sa.bindparam('documento', documento), sa.bindparam('condicion', condicion),
            sa.bindparam('codigos', codigos, type_=CODIGOS), sa.bindparam('dentro', dentro)]


def _borrar(documento: str, condicion: str, codigos: list[str], dentro: bool = True) -> None:
    op.execute(sa.text(f"DELETE FROM tramite_documentos WHERE {_FILAS}")
               .bindparams(*_parametros(documento, condicion, codigos, dentro)))


def _rangos(rangos: list[str] | None, documento: str, condicion: str, codigos: list[str], dentro: bool = True) -> None:
    op.execute(sa.text(f"UPDATE tramite_documentos SET rangos = :rangos WHERE {_FILAS}")
               .bindparams(sa.bindparam('rangos', rangos, type_=RANGOS),
                           *_parametros(documento, condicion, codigos, dentro)))


def _al_final(documento: str, condicion: str, rangos: list[str] | None, codigos: list[str], dentro: bool = True) -> None:
    """Una fila al final del checklist de cada trámite elegido. Si el trámite ya tiene ese
    documento (una fila por documento), la deja como está."""
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, rangos, orden)
        SELECT t.id, d.id, 'marino', :condicion, :rangos,
               COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1
          FROM tipos_tramite t, documentos_requeridos d
         WHERE (t.codigo = ANY(:codigos)) = :dentro AND d.codigo = :documento
        ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
    """).bindparams(sa.bindparam('rangos', rangos, type_=RANGOS), *_parametros(documento, condicion, codigos, dentro)))


def _pregunta(valor: bool) -> None:
    op.execute(sa.text("UPDATE tipos_tramite SET permite_subir_y_bajar = :valor WHERE codigo = ANY(:codigos)")
               .bindparams(sa.bindparam('valor', valor), sa.bindparam('codigos', EMBARQUE_DESEMBARQUE, type_=CODIGOS)))


def upgrade() -> None:
    # «Subir y bajar», de Embarque y Desembarque al trámite de Técnico.
    _pregunta(False)
    _borrar(CARTA, 'subir_y_bajar', EMBARQUE_DESEMBARQUE)
    _al_final(CARTA, 'subir_y_bajar', None, [TECNICO])

    # La «Visa»: en Técnico, a todos sus rangos; en los demás, al Militar; en Shore Pass, a nadie.
    _rangos(['militar'], VISA, 'nacionalidad_restringida', [TECNICO, SHORE_PASS], dentro=False)
    _borrar(VISA, 'nacionalidad_restringida', [SHORE_PASS])

    # La Visa Especial de Marino al Marino y al Pasajero restringidos de los demás trámites.
    _al_final(VISA_MARINO, 'nacionalidad_restringida', ['marino', 'pasajero'], [TECNICO], dentro=False)


def downgrade() -> None:
    _borrar(VISA_MARINO, 'nacionalidad_restringida', [TECNICO], dentro=False)
    _al_final(VISA, 'nacionalidad_restringida', None, [SHORE_PASS])
    _rangos(None, VISA, 'nacionalidad_restringida', [TECNICO], dentro=False)

    _borrar(CARTA, 'subir_y_bajar', [TECNICO])
    _pregunta(True)
    _al_final(CARTA, 'subir_y_bajar', None, EMBARQUE_DESEMBARQUE)
