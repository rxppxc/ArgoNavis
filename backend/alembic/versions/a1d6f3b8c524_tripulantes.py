"""tripulantes

«Pasajeros» vuelve a ser «tripulantes» en lo que ve el usuario (pedido del usuario del
2026-11-18: «tripulante» es la forma general de llamar a todos los rangos). Deshace los
textos del catálogo de la revisión `d5b8e2f1a9c3` (2026-11-10):

  - la descripción de cada trámite (las tarjetas del paso 1 del formulario);
  - la del Formulario No. 3, la del Formulario No. 6 de custodia y la de la Visa;
  - la del permiso de la agencia (T-CREAR-BASICA).

El rango «Pasajero» (2026-11-13) conserva su nombre: es un rango, no la forma general.
Ninguno de estos textos lo nombra.

Revision ID: a1d6f3b8c524
Revises: f4c9b2e7a813
Create Date: 2026-11-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a1d6f3b8c524'
down_revision: Union[str, None] = 'f4c9b2e7a813'
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
    _cambiar('pasajero', 'tripulante')


def downgrade() -> None:
    _cambiar('tripulante', 'pasajero')
