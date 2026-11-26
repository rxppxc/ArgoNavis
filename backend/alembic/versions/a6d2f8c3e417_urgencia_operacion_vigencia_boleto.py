"""Urgencia médica con operación, vigencia de 120 horas y una Carta Form. 7; boleto opcional

Revision ID: a6d2f8c3e417
Revises: d7f3b0c5e849
Create Date: 2026-11-26

Pedido del usuario (2026-11-26):

  - La copia del boleto aéreo es opcional en Desembarque y en el trámite de Técnico, para
    todos los rangos a los que se pide (`tramite_documentos.rangos_opcional`). En los demás
    trámites se sigue exigiendo.
  - En Urgencia médica:
      - la Carta de Responsabilidad (Form. No. 7) pasa a ser una por solicitud, con los
        documentos de la solicitud, en vez de una por tripulante. Se sigue pidiendo solo si
        hay algún Marino o Pasajero (sus `rangos`);
      - el formulario pide la operación como el trámite de Técnico (`pide_operacion`): solo
        se registra, no cambia los documentos;
      - la autorización vale exactamente 120 horas desde la aprobación
        (`tipos_tramite.horas_vigencia`; nula = como siempre, hasta el final del día dos días
        después de la operación).

Las solicitudes ya enviadas conservan la foto del checklist con el que se enviaron
(`solicitud_casillas`) y su `vigente_hasta`: nada de esto las cambia.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a6d2f8c3e417'
down_revision: Union[str, None] = 'd7f3b0c5e849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

URGENCIA = "(SELECT id FROM tipos_tramite WHERE codigo = 'F3-URGENCIA-MEDICA')"


def _fila(tramite: str, documento: str) -> str:
    return (f"tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = '{tramite}') "
            f"AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = '{documento}')")


def upgrade() -> None:
    op.add_column('tipos_tramite', sa.Column('horas_vigencia', sa.Integer(), nullable=True))
    op.execute(f"UPDATE tipos_tramite SET pide_operacion = true, horas_vigencia = 120 WHERE id = {URGENCIA}")
    op.execute(f"UPDATE tramite_documentos SET alcance = 'solicitud' "
               f"WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-FORM7-RESPONSABILIDAD')}")
    op.execute("UPDATE tramite_documentos SET rangos_opcional = ARRAY['marino', 'pasajero', 'militar']::varchar[] "
               f"WHERE {_fila('F3-DESEMBARQUE', 'DOC-BOLETO-AEREO')}")
    op.execute("UPDATE tramite_documentos SET rangos_opcional = "
               "ARRAY['tecnico', 'supernumerario', 'superintendente']::varchar[] "
               f"WHERE {_fila('F3-TECNICO', 'DOC-BOLETO-AEREO')}")


def downgrade() -> None:
    op.execute(f"UPDATE tramite_documentos SET rangos_opcional = NULL WHERE {_fila('F3-TECNICO', 'DOC-BOLETO-AEREO')}")
    op.execute(f"UPDATE tramite_documentos SET rangos_opcional = NULL WHERE {_fila('F3-DESEMBARQUE', 'DOC-BOLETO-AEREO')}")
    op.execute(f"UPDATE tramite_documentos SET alcance = 'marino' "
               f"WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-FORM7-RESPONSABILIDAD')}")
    op.execute(f"UPDATE tipos_tramite SET pide_operacion = false WHERE id = {URGENCIA}")
    op.drop_column('tipos_tramite', 'horas_vigencia')
