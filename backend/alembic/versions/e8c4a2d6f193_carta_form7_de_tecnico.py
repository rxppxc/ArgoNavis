"""La Carta Form. No. 7 del trámite de Técnico, con sus rangos en el nombre

Revision ID: e8c4a2d6f193
Revises: b7d3e9a5c261
Create Date: 2026-11-26

Pedido del usuario (2026-11-26, después de b7d3e9a5c261): la Carta de Responsabilidad
(Form. No. 7) que pide «Subir y bajar» en la Autorización de Técnico, Superintendente o
Supernumerario, una por solicitud, lleva en el nombre los rangos del trámite: «Carta de
Responsabilidad (Form. No. 7) de Técnico, Superintendente o Supernumerario». Es un documento
propio (DOC-FORM7-TECNICO): la carta de los demás trámites (DOC-FORM7-RESPONSABILIDAD), la de
Renovación y la de Urgencia médica, no cambia de nombre.

Las solicitudes ya enviadas conservan la foto de su checklist (`solicitud_casillas`), con la
carta de siempre.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8c4a2d6f193'
down_revision: Union[str, None] = 'b7d3e9a5c261'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CARTA = 'DOC-FORM7-RESPONSABILIDAD'
CARTA_TECNICO = 'DOC-FORM7-TECNICO'
NOMBRE = 'Carta de Responsabilidad (Form. No. 7) de Técnico, Superintendente o Supernumerario'
DESCRIPCION = 'Una por solicitud, para todos los tripulantes. Con la operación «Subir y bajar».'


def _documento(codigo: str) -> str:
    return f"(SELECT id FROM documentos_requeridos WHERE codigo = '{codigo}')"


def _fila_de_tecnico(documento: str) -> str:
    return (f"tipo_tramite_id = (SELECT id FROM tipos_tramite WHERE codigo = 'F3-TECNICO') "
            f"AND documento_id = {_documento(documento)}")


def upgrade() -> None:
    op.execute(sa.text("""
        INSERT INTO documentos_requeridos (codigo, nombre, descripcion, requiere_libreta)
        VALUES (:codigo, :nombre, :descripcion, false)
        ON CONFLICT (codigo) DO NOTHING
    """).bindparams(codigo=CARTA_TECNICO, nombre=NOMBRE, descripcion=DESCRIPCION))
    # La misma fila del trámite (su orden, su alcance y su condición), con la carta propia.
    op.execute(f"UPDATE tramite_documentos SET documento_id = {_documento(CARTA_TECNICO)} "
               f"WHERE {_fila_de_tecnico(CARTA)}")


def downgrade() -> None:
    op.execute(f"UPDATE tramite_documentos SET documento_id = {_documento(CARTA)} "
               f"WHERE {_fila_de_tecnico(CARTA_TECNICO)}")
    # La carta propia se borra solo si ninguna solicitud la usó (la foto y los archivos la referencian).
    op.execute(sa.text("""
        DELETE FROM documentos_requeridos d
         WHERE d.codigo = :codigo
           AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
           AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
    """).bindparams(codigo=CARTA_TECNICO))
