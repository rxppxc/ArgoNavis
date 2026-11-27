"""Urgencia médica: sin operación ni puerto de desembarque, con 5 días de sellado y la Form. 7 para todos

Revision ID: a3c8e5f1b296
Revises: f2b6d9c4a738
Create Date: 2026-11-27

Decisión del usuario (2026-11-27), sobre la lectura literal del Form. 3:
- Urgencia médica ya no pide la operación (Embarque o Desembarque, que pedía desde el 2026-11-26)
  ni el puerto de desembarque.
- Pide los días del sellado, como Shore Pass, pero solo 5, que el formulario trae elegido: la columna
  nueva `tipos_tramite.dias_sellado_opciones` dice cuáles ofrece cada trámite (nula = 5 o 15). La
  autorización sigue valiendo 120 horas desde la aprobación.
- La Carta de Responsabilidad (Form. No. 7), una por solicitud, se pide sea cual sea el rango: hasta
  hoy, solo si había algún Marino o Pasajero (sus `rangos`).

Las solicitudes ya enviadas conservan su operación, su puerto de desembarque y la foto de su checklist.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3c8e5f1b296'
down_revision: Union[str, None] = 'f2b6d9c4a738'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

URGENCIA = "codigo = 'F3-URGENCIA-MEDICA'"
CARTA_DE_URGENCIA = ("tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-URGENCIA-MEDICA') "
                     "AND documento_id = (SELECT id FROM documentos_requeridos "
                     "WHERE codigo = 'DOC-FORM7-RESPONSABILIDAD')")


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('dias_sellado_opciones', postgresql.ARRAY(sa.Integer()), nullable=True))
    op.execute("UPDATE tipos_tramite SET pide_operacion = false, operaciones = NULL, "
               "requiere_puerto_desembarque = false, pide_dias_sellado = true, "
               f"dias_sellado_opciones = ARRAY[5] WHERE {URGENCIA}")
    op.execute(f"UPDATE tramite_documentos SET rangos = NULL WHERE {CARTA_DE_URGENCIA}")


def downgrade() -> None:
    op.execute(f"UPDATE tramite_documentos SET rangos = ARRAY['marino', 'pasajero']::varchar[] "
               f"WHERE {CARTA_DE_URGENCIA}")
    op.execute("UPDATE tipos_tramite SET pide_operacion = true, "
               "operaciones = ARRAY['embarque', 'desembarque']::varchar[], "
               f"requiere_puerto_desembarque = true, pide_dias_sellado = false WHERE {URGENCIA}")
    op.drop_column('tipos_tramite', 'dias_sellado_opciones')
