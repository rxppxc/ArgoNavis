"""La Carta Form. No. 7 del trámite de Técnico, en las tres operaciones

Revision ID: f2b6d9c4a738
Revises: e8c4a2d6f193
Create Date: 2026-11-27

Pedido del usuario (2026-11-27): en la Autorización de Técnico, Superintendente o Supernumerario,
la Carta de Responsabilidad (Form. No. 7) es obligatoria con cualquier operación (Embarque,
Desembarque o Subir y bajar), una por solicitud. Del 2026-11-18 al 27 se pedía solo con «Subir y
bajar» (la condición `subir_y_bajar`, que sigue en la carta de garantía de la agencia contratante).

Las solicitudes ya enviadas conservan la foto de su checklist (`solicitud_casillas`): las de
Embarque y Desembarque sin la carta no quedan incompletas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2b6d9c4a738'
down_revision: Union[str, None] = 'e8c4a2d6f193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CARTA_TECNICO = 'DOC-FORM7-TECNICO'
DESCRIPCION = 'Una por solicitud, para todos los tripulantes.'
DESCRIPCION_ANTERIOR = 'Una por solicitud, para todos los tripulantes. Con la operación «Subir y bajar».'

_FILA = (f"tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-TECNICO') "
         f"AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = '{CARTA_TECNICO}')")


def _cambiar(condicion: str, descripcion: str) -> None:
    op.execute(f"UPDATE tramite_documentos SET condicion = '{condicion}' WHERE {_FILA}")
    op.execute(sa.text("UPDATE documentos_requeridos SET descripcion = :descripcion WHERE codigo = :codigo")
               .bindparams(descripcion=descripcion, codigo=CARTA_TECNICO))


def upgrade() -> None:
    _cambiar('siempre', DESCRIPCION)


def downgrade() -> None:
    _cambiar('subir_y_bajar', DESCRIPCION_ANTERIOR)
