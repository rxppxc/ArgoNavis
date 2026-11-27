"""Form. No. 7 de «Subir y bajar», una por solicitud; sin boleto en Embarque ni en Renovación

Revision ID: b7d3e9a5c261
Revises: c5f2a9d7e184
Create Date: 2026-11-26

Pedido del usuario (2026-11-26, tercer lote):

  - En el trámite de Técnico, con la operación «Subir y bajar», la Carta de Responsabilidad
    (Form. No. 7) pasa a ser una por solicitud, con los documentos de la solicitud, junto a la
    carta de garantía de la agencia contratante. Antes, una por tripulante (2026-11-18).
  - Embarque ya no pide la copia del boleto aéreo (se le pedía solo al Militar extranjero).
  - Renovación de pasaporte tampoco: los rangos que no son Marino (técnico, supernumerario,
    superintendente y militar) presentan solo las Generales de pasaporte.

Urgencia médica y Cambio de nave siguen pidiendo el boleto a los rangos que no son Marino
(decisión del usuario). Las solicitudes ya enviadas conservan la foto de su checklist
(`solicitud_casillas`): nada de esto las cambia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d3e9a5c261'
down_revision: Union[str, None] = 'c5f2a9d7e184'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOLETO = "(SELECT id FROM documentos_requeridos WHERE codigo = 'DOC-BOLETO-AEREO')"
# Las filas del boleto que se quitan, como estaban (para volver atrás): (trámite, condición, rangos).
BOLETOS = (
    ('F3-EMBARQUE', 'solo_extranjeros', ['militar']),
    ('F3-RENOV-PASAPORTE', 'siempre', ['militar', 'tecnico', 'supernumerario', 'superintendente']),
)


def _fila(tramite: str, documento: str) -> str:
    return (f"tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = '{tramite}') "
            f"AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = '{documento}')")


def upgrade() -> None:
    op.execute(f"UPDATE tramite_documentos SET alcance = 'solicitud' "
               f"WHERE {_fila('F3-TECNICO', 'DOC-FORM7-RESPONSABILIDAD')}")
    for tramite, _, _ in BOLETOS:
        op.execute(f"DELETE FROM tramite_documentos WHERE {_fila(tramite, 'DOC-BOLETO-AEREO')}")


def downgrade() -> None:
    # Vuelven al final de su trámite: el orden solo cambia dónde se muestran.
    for tramite, condicion, rangos in BOLETOS:
        op.execute(sa.text(f"""
            INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
            SELECT t.id, {BOLETO}, 'marino', :condicion,
                   COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1,
                   CAST(:rangos AS varchar[])
              FROM tipos_tramite t WHERE t.codigo = :codigo
        """).bindparams(codigo=tramite, condicion=condicion, rangos='{' + ','.join(rangos) + '}'))
    op.execute(f"UPDATE tramite_documentos SET alcance = 'marino' "
               f"WHERE {_fila('F3-TECNICO', 'DOC-FORM7-RESPONSABILIDAD')}")
