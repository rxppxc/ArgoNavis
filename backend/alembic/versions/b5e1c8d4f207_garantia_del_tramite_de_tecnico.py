"""La carta de garantía del trámite de Técnico, según la operación

Revision ID: b5e1c8d4f207
Revises: a1d6f3b8c524
Create Date: 2026-11-18

Pedido del usuario (2026-11-18), en la Autorización de Técnico, Superintendente o
Supernumerario, una por solicitud:

  - con la operación Embarque o Desembarque, la «Carta de garantía de la agencia
    contratante o contrato» (cualquiera de los dos, en una casilla; condición nueva
    `embarque_o_desembarque`);
  - con «Subir y bajar», la «Carta de garantía de la agencia contratante» (condición
    `subir_y_bajar`), además de la Carta de Responsabilidad (Form. No. 7) de cada
    tripulante, que se sigue pidiendo (decisión del usuario: las dos).

Las solicitudes ya enviadas conservan su foto del checklist; una devuelta se corrige con
las reglas nuevas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e1c8d4f207'
down_revision: Union[str, None] = 'a1d6f3b8c524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TECNICO = 'F3-TECNICO'
# (código, nombre, descripción, condición en el trámite de Técnico)
DOCUMENTOS = [
    ('DOC-GARANTIA-O-CONTRATO', 'Carta de garantía de la agencia contratante o contrato',
     'Una por solicitud, para todos los tripulantes: la carta o el contrato.', 'embarque_o_desembarque'),
    ('DOC-CARTA-GARANTIA', 'Carta de garantía de la agencia contratante',
     'Una por solicitud, para todos los tripulantes.', 'subir_y_bajar'),
]


def upgrade() -> None:
    for codigo, nombre, descripcion, condicion in DOCUMENTOS:
        op.execute(sa.text("""
            INSERT INTO documentos_requeridos (codigo, nombre, descripcion, requiere_libreta)
            VALUES (:codigo, :nombre, :descripcion, false)
            ON CONFLICT (codigo) DO NOTHING
        """).bindparams(codigo=codigo, nombre=nombre, descripcion=descripcion))
        # Al final del checklist del trámite, después del Formulario No. 3.
        op.execute(sa.text("""
            INSERT INTO tramite_documentos (tipo_tramite_id, documento_id, alcance, condicion, orden)
            SELECT t.id, d.id, 'solicitud', :condicion,
                   COALESCE((SELECT max(x.orden) FROM tramite_documentos x WHERE x.tipo_tramite_id = t.id), 0) + 1
              FROM tipos_tramite t, documentos_requeridos d
             WHERE t.codigo = :tramite AND d.codigo = :codigo
            ON CONFLICT ON CONSTRAINT uq_tramite_documento DO NOTHING
        """).bindparams(condicion=condicion, tramite=TECNICO, codigo=codigo))


def downgrade() -> None:
    for codigo, _nombre, _descripcion, _condicion in DOCUMENTOS:
        op.execute(sa.text("""
            DELETE FROM tramite_documentos
             WHERE documento_id = (SELECT id FROM documentos_requeridos WHERE codigo = :codigo)
        """).bindparams(codigo=codigo))
        # El documento se borra solo si ninguna solicitud lo usó (la foto y los archivos lo referencian).
        op.execute(sa.text("""
            DELETE FROM documentos_requeridos d
             WHERE d.codigo = :codigo
               AND NOT EXISTS (SELECT 1 FROM solicitud_casillas c WHERE c.documento_id = d.id)
               AND NOT EXISTS (SELECT 1 FROM solicitud_documentos s WHERE s.documento_id = d.id)
        """).bindparams(codigo=codigo))
