"""Los modelos (las tablas). Importar cualquiera los trae todos (2026-11-22).

Las relaciones se nombran por texto ("AgenciaNaviera") y SQLAlchemy las resuelve en la primera
consulta: si una clase no está cargada, falla. La aplicación las cargaba todas en main.py, pero
una orden de consola que corre sola (asignar_rol) no, y se caía. Un modelo nuevo va aquí; lo
prueba tests/test_consola.py."""
from app.domain.models import audit_log, boleta, catalogo, correo, rol, solicitud, tramite, user  # noqa: F401
