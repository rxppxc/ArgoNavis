"""Uso del sistema (no del flujo): cuentas, agencias y documentos almacenados.

Lo muestra la página de Estadísticas (/admin/stats) y va también en sus
exportaciones (/solicitudes/estadisticas/exportar). Antes se armaba dentro del
endpoint de /admin/stats.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.catalogo_repository import RepositorioCatalogo
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.domain.repositories.user_repository import RepositorioUsuario
from app.domain.schemas.solicitud import FilaTopAgencia, SalidaUsoSistema


class ServicioUsoSistema:
    def __init__(self, sesion: AsyncSession) -> None:
        self.sesion = sesion

    async def resumen(self) -> SalidaUsoSistema:
        """Totales a hoy: no dependen de ningún periodo."""
        repo_solicitudes = RepositorioSolicitud(self.sesion)
        usuarios, activos = await RepositorioUsuario(self.sesion).contar()
        documentos, almacenamiento_bytes = await repo_solicitudes.totales_documentos()
        return SalidaUsoSistema(
            usuarios=usuarios,
            usuarios_activos=activos,
            agencias=await RepositorioCatalogo(self.sesion).contar_agencias(),
            documentos=documentos,
            almacenamiento_bytes=almacenamiento_bytes,
            top_agencias=[
                FilaTopAgencia(agencia_id=f.agencia_id, nombre=f.agencia_nombre, total=f.total)
                for f in await repo_solicitudes.top_agencias()
            ],
        )
