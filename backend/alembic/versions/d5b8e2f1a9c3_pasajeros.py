"""pasajeros

«A los marinos tripulantes ahora se les llama pasajeros» (pedido del usuario del
2026-11-10). Cambia los textos del catálogo que se ven en pantalla:

  - la descripción de cada trámite (las tarjetas del paso 1 del formulario);
  - la del Formulario No. 6 de custodia;
  - la del permiso de la agencia (T-CREAR-BASICA).

No cambian el nombre oficial del documento «Lista de Tripulantes» del
Formulario No. 3 (decisión del usuario: hasta que UCVMM cambie el formulario)
ni los nombres de las tablas y columnas (`solicitud_tripulantes`,
`cantidad_tripulantes`), que son el contrato con el código.

Revision ID: d5b8e2f1a9c3
Revises: c1f7a3e9d2b6
Create Date: 2026-11-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd5b8e2f1a9c3'
down_revision: Union[str, None] = 'c1f7a3e9d2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columnas con texto para el usuario (nombres fijos: no vienen de afuera).
COLUMNAS = [('tipos_tramite', 'descripcion'), ('documentos_requeridos', 'descripcion'), ('permisos', 'descripcion')]


def _cambiar(antes: str, despues: str) -> None:
    """Reemplaza la palabra con mayúscula y en minúscula (el plural va solo: «-s»)."""
    for tabla, columna in COLUMNAS:
        op.execute(sa.text(
            f"UPDATE {tabla} SET {columna} = replace(replace({columna}, :am, :dm), :a, :d) "
            f"WHERE {columna} ILIKE :patron"
        ).bindparams(am=antes.capitalize(), dm=despues.capitalize(), a=antes, d=despues, patron=f"%{antes}%"))


def upgrade() -> None:
    _cambiar('tripulante', 'pasajero')


def downgrade() -> None:
    _cambiar('pasajero', 'tripulante')
