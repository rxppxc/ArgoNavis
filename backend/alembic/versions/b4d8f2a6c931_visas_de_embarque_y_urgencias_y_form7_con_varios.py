"""Visas de Embarque y Urgencias, Urgencias sin boleto y la Form. 7 con varios archivos

Revision ID: b4d8f2a6c931
Revises: a3c8e5f1b296
Create Date: 2026-11-27

Pedido del usuario (2026-11-27), sobre la lectura literal del Form. 3:
- Embarque: la Visa Especial de Marino solo al Marino extranjero (antes también al Pasajero); al
  Pasajero y al Militar de nacionalidad restringida, la «Visa».
- Urgencias: el Reporte médico a todos los rangos (antes, al Marino y al Pasajero); sin el boleto aéreo
  del Militar, el Técnico y los Supers; sin la Visa Especial de Marino del Marino y el Pasajero
  restringidos; la «Visa» a los restringidos que no son Marino.
- Renovación de pasaporte: la Carta de Responsabilidad (Form. No. 7), una por solicitud y para cualquier
  rango (antes, una por tripulante, al Marino y al Pasajero).
- La Form. 7 de Renovación, Urgencias y Técnico, una obligatoria y hasta 9 opcionales más en la misma
  casilla: la columna nueva `tramite_documentos.maximo_archivos` (1 por defecto; ahí, 10).

Las solicitudes ya enviadas conservan la foto de su checklist (`solicitud_casillas`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d8f2a6c931'
down_revision: Union[str, None] = 'a3c8e5f1b296'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fila(tramite: str, documento: str, extra: str = "") -> str:
    return (f"tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = '{tramite}') "
            f"AND documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = '{documento}'){extra}")


def _insertar(tramite: str, documento: str, condicion: str, orden: int, rangos: list[str]) -> None:
    op.execute(sa.text("""
        INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden, rangos)
        SELECT t.id, d.id, 'marino', :condicion, :orden, CAST(:rangos AS varchar[])
          FROM tipos_tramite t, documentos_requeridos d
         WHERE t.codigo = :tramite AND d.codigo = :documento
    """).bindparams(tramite=tramite, documento=documento, condicion=condicion, orden=orden,
                    rangos="{" + ",".join(rangos) + "}"))


NO_MARINOS = ['militar', 'tecnico', 'supernumerario', 'superintendente']
CARTAS = [('F3-RENOV-PASAPORTE', 'DOC-FORM7-RESPONSABILIDAD'), ('F3-URGENCIA-MEDICA', 'DOC-FORM7-RESPONSABILIDAD'),
          ('F3-TECNICO', 'DOC-FORM7-TECNICO')]


def upgrade() -> None:
    op.add_column('tramite_documentos', sa.Column('maximo_archivos', sa.Integer(), nullable=False,
                                                  server_default='1'))
    for tramite, documento in CARTAS:
        op.execute(f"UPDATE tramite_documentos SET maximo_archivos = 10 WHERE {_fila(tramite, documento)}")

    # Embarque: la Visa Especial de Marino, solo al Marino; la «Visa», al Pasajero y al Militar restringidos.
    op.execute("UPDATE tramite_documentos SET rangos = ARRAY['marino']::varchar[] "
               f"WHERE {_fila('F3-EMBARQUE', 'DOC-VISA-MARINO')}")
    _insertar('F3-EMBARQUE', 'DOC-VISA', 'nacionalidad_restringida', 4, ['militar', 'pasajero'])

    # Urgencias: el Reporte médico a todos; sin boleto ni Visa Especial de Marino; la «Visa» a los demás.
    op.execute(f"UPDATE tramite_documentos SET rangos = NULL WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-REPORTE-MEDICO')}")
    op.execute(f"DELETE FROM tramite_documentos WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-BOLETO-AEREO')}")
    op.execute(f"DELETE FROM tramite_documentos WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-VISA-MARINO')}")
    _insertar('F3-URGENCIA-MEDICA', 'DOC-VISA', 'nacionalidad_restringida', 7, ['pasajero'] + NO_MARINOS)

    # Renovación: la Form. 7, una por solicitud y para cualquier rango.
    op.execute("UPDATE tramite_documentos SET alcance = 'solicitud', rangos = NULL "
               f"WHERE {_fila('F3-RENOV-PASAPORTE', 'DOC-FORM7-RESPONSABILIDAD')}")


def downgrade() -> None:
    op.execute("UPDATE tramite_documentos SET alcance = 'marino', rangos = ARRAY['marino', 'pasajero']::varchar[] "
               f"WHERE {_fila('F3-RENOV-PASAPORTE', 'DOC-FORM7-RESPONSABILIDAD')}")

    op.execute(f"DELETE FROM tramite_documentos WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-VISA')}")
    _insertar('F3-URGENCIA-MEDICA', 'DOC-VISA-MARINO', 'nacionalidad_restringida', 7, ['marino', 'pasajero'])
    _insertar('F3-URGENCIA-MEDICA', 'DOC-BOLETO-AEREO', 'siempre', 5, NO_MARINOS)
    op.execute("UPDATE tramite_documentos SET rangos = ARRAY['marino', 'pasajero']::varchar[] "
               f"WHERE {_fila('F3-URGENCIA-MEDICA', 'DOC-REPORTE-MEDICO')}")

    op.execute(f"DELETE FROM tramite_documentos WHERE {_fila('F3-EMBARQUE', 'DOC-VISA')}")
    op.execute("UPDATE tramite_documentos SET rangos = ARRAY['marino', 'pasajero']::varchar[] "
               f"WHERE {_fila('F3-EMBARQUE', 'DOC-VISA-MARINO')}")

    op.drop_column('tramite_documentos', 'maximo_archivos')
