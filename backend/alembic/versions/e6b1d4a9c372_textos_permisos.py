"""Textos de los permisos al día con el flujo.

T-FINALIZAR-PUERTO decía que el puesto «registra comentarios»: el comentario
sin finalizar se retiró el 2026-10-20 (solo queda el de la finalización).
T-PROCESAR-PACIFICO decía «niega»: en pantalla la acción es «Denegar».

Revision ID: e6b1d4a9c372
Revises: a3d9c6e1f584
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op

revision = "e6b1d4a9c372"
down_revision = "a3d9c6e1f584"
branch_labels = None
depends_on = None

NUEVOS = {
    "T-FINALIZAR-PUERTO": "Ve las autorizaciones aprobadas de los puestos de control que tiene asignados "
                          "y las finaliza, indicando dónde terminó la operación.",
    "T-PROCESAR-PACIFICO": "Revisa las solicitudes de autorización marítima: verifica impedimentos, "
                           "aprueba, deniega o devuelve a corrección.",
}

ANTERIORES = {
    "T-FINALIZAR-PUERTO": "Ve las autorizaciones aprobadas de los puestos de control que tiene asignados, "
                          "registra comentarios y las finaliza.",
    "T-PROCESAR-PACIFICO": "Revisa las solicitudes de autorización marítima: verifica impedimentos, "
                           "aprueba, niega o devuelve a corrección.",
}


def _aplicar(textos: dict[str, str]) -> None:
    cx = op.get_bind()
    for codigo, descripcion in textos.items():
        cx.execute(sa.text("UPDATE permisos SET descripcion = :descripcion WHERE codigo = :codigo"),
                   {"descripcion": descripcion, "codigo": codigo})


def upgrade() -> None:
    _aplicar(NUEVOS)


def downgrade() -> None:
    _aplicar(ANTERIORES)
