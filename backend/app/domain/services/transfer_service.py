import logging
import re
import secrets
import shutil
import unicodedata
import asyncio
import aiofiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
from app.core.config import obtener_configuracion
from app.domain.models.transfer import Transferencia, ArchivoTransferencia, EstadoTransferencia
from app.domain.repositories.transfer_repository import RepositorioTransferencia
from app.domain.schemas.transfer import (
    DatosCrearTransferencia, SalidaTransferencia, RespuestaTransferenciaPublica,
)

try:
    import magic  # type: ignore
    _MAGIC_DISPONIBLE = True
except Exception:  # pragma: no cover — libmagic no disponible
    magic = None  # type: ignore
    _MAGIC_DISPONIBLE = False

try:
    from oletools.olevba import VBA_Parser  # type: ignore
    _OLETOOLS_DISPONIBLE = True
except Exception:  # pragma: no cover — oletools no disponible
    VBA_Parser = None  # type: ignore
    _OLETOOLS_DISPONIBLE = False

logger        = logging.getLogger(__name__)
configuracion = obtener_configuracion()

_TZ_PANAMA   = ZoneInfo("America/Panama")
TAMANO_CHUNK = 1024 * 1024  # 1 MB por fragmento

# Caracteres prohibidos en nombres de archivo (control + reservados de Windows
# + comillas y diagonales). Se reemplazan por "_".
_NOMBRE_INVALIDO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

EXTENSIONES_PERMITIDAS = {
    # Documentos de oficina — tanto el formato legado (OLE2) como el moderno
    # (OOXML). Ambos se escanean en busca de macros VBA antes de aceptarlos
    # (ver _EXTENSIONES_CON_MACROS_POSIBLES / _verificar_sin_macros). No se
    # permiten variantes "habilitadas para macros" (.docm/.xlsm): esas ya
    # declaran en la extensión que pueden traer macros, no tiene sentido
    # aceptarlas y luego rechazarlas casi siempre.
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    # Imágenes (sin .svg: puede llevar <script> embebido — riesgo XSS)
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff",
    ".heic", ".heif", ".avif",
}

# Extensiones que pueden llevar macros VBA embebidas (contenedores OLE2 o
# OOXML). Se escanean con oletools antes de aceptarlas.
_EXTENSIONES_CON_MACROS_POSIBLES = {".doc", ".xls", ".docx", ".xlsx"}

# MIME conocidos por extensión. Si python-magic está disponible se prefiere lo
# que detecta del contenido. Si no, este mapa actúa de respaldo confiable.
_MIME_POR_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".avif": "image/avif",
}


def _sanear_nombre(nombre: str) -> str:
    """Devuelve un nombre de archivo seguro: sin caracteres de control, sin
    barras, sin caracteres reservados en NTFS. Conserva tildes y unicode."""
    nombre = unicodedata.normalize("NFC", nombre or "")
    nombre = nombre.replace("\r", " ").replace("\n", " ")
    nombre = _NOMBRE_INVALIDO.sub("_", nombre)
    nombre = nombre.strip(" .")
    return nombre or "archivo"


def _detectar_mime(ruta: Path, ext: str) -> str:
    """Detecta MIME por contenido (python-magic) y cae al mapa por extensión
    si la librería no está disponible. Nunca confía en el header del cliente."""
    if _MAGIC_DISPONIBLE:
        try:
            mime = magic.from_file(str(ruta), mime=True)
            if mime and mime != "application/octet-stream":
                return mime
        except Exception as exc:  # pragma: no cover
            logger.warning("[mime] Detección por contenido falló: %s", exc)
    return _MIME_POR_EXTENSION.get(ext.lower(), "application/octet-stream")


def _tiene_macros_sync(ruta: Path) -> bool:
    """Analiza un archivo OLE2 (.doc/.xls) en busca de macros VBA. Síncrono
    y potencialmente lento — llamar siempre vía asyncio.to_thread()."""
    parser = VBA_Parser(str(ruta))
    try:
        return parser.detect_vba_macros()
    finally:
        parser.close()


async def _verificar_sin_macros(ruta: Path, ext: str, nombre_original: str) -> None:
    """Rechaza archivos .doc/.xls que contengan macros VBA. Falla cerrado: si
    oletools no está disponible o no puede analizar el archivo, se rechaza
    igual — preferimos un falso rechazo a aceptar un archivo sin garantías."""
    if ext not in _EXTENSIONES_CON_MACROS_POSIBLES:
        return
    if not _OLETOOLS_DISPONIBLE:
        logger.error("[macros] oletools no disponible — rechazando '%s' por precaución.", nombre_original)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar el archivo de forma segura. Contacta al administrador.",
        )
    try:
        tiene_macros = await asyncio.to_thread(_tiene_macros_sync, ruta)
    except Exception as exc:
        logger.warning("[macros] No se pudo analizar '%s': %s", nombre_original, exc)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"No se pudo validar '{nombre_original}' de forma segura — el archivo podría estar dañado o no ser un documento Office válido.",
        )
    if tiene_macros:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{nombre_original}' contiene macros y no está permitido. Guárdalo sin macros e intenta de nuevo.",
        )


def _expira_a_medianoche(dias: int) -> datetime:
    dia_final = (datetime.now(_TZ_PANAMA) + timedelta(days=dias)).date()
    return datetime(dia_final.year, dia_final.month, dia_final.day,
                    23, 59, 59, tzinfo=_TZ_PANAMA)


def _validar_extension(nombre_archivo: str) -> str:
    """Devuelve la extensión en minúsculas si está permitida; lanza HTTPException si no."""
    ext = Path(nombre_archivo).suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"El tipo de archivo '{ext or 'sin extensión'}' no está permitido.",
        )
    return ext


class ServicioTransferencia:
    def __init__(self, repo: RepositorioTransferencia):
        self.repo = repo

    async def _guardar_archivos(
        self, destino: Path, archivos_subidos: list[UploadFile],
        user_id: int, es_original: bool,
    ) -> list[ArchivoTransferencia]:
        """Guarda los archivos en disco y devuelve los registros listos."""
        max_bytes = configuracion.MAX_FILE_SIZE_MB * 1024 * 1024
        guardados: list[ArchivoTransferencia] = []
        for subida in archivos_subidos:
            nombre_original   = _sanear_nombre(subida.filename or "archivo")
            ext               = _validar_extension(nombre_original)
            nombre_almacenado = f"{secrets.token_hex(16)}{ext}"
            ruta_archivo      = destino / nombre_almacenado
            tamano            = 0

            async with aiofiles.open(ruta_archivo, "wb") as f:
                while True:
                    fragmento = await subida.read(TAMANO_CHUNK)
                    if not fragmento:
                        break
                    tamano += len(fragmento)
                    if tamano > max_bytes:
                        try:
                            ruta_archivo.unlink(missing_ok=True)
                        except OSError as exc:
                            logger.warning("[storage] No se pudo eliminar %s: %s", ruta_archivo, exc)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"El archivo '{nombre_original}' supera el límite de {configuracion.MAX_FILE_SIZE_MB} MB.",
                        )
                    await f.write(fragmento)

            # .doc/.xls: rechazar si tienen macros VBA embebidas
            try:
                await _verificar_sin_macros(ruta_archivo, ext, nombre_original)
            except HTTPException:
                ruta_archivo.unlink(missing_ok=True)
                raise

            # MIME desde el contenido (no confiamos en lo que mande el cliente)
            mime_real = _detectar_mime(ruta_archivo, ext)

            guardados.append(ArchivoTransferencia(
                original_name = nombre_original,
                stored_name   = nombre_almacenado,
                path          = str(ruta_archivo),
                mime_type     = mime_real,
                size          = tamano,
                subido_por_id = user_id,
                es_original   = es_original,
            ))
        return guardados

    async def crear(self, user_id: int, datos: DatosCrearTransferencia, archivos_subidos: list[UploadFile]) -> SalidaTransferencia:
        """Sube archivos y quedan disponibles de inmediato (storage simple:
        sin borrador ni revisión previa)."""
        if not archivos_subidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes adjuntar al menos un archivo.",
            )

        token   = secrets.token_urlsafe(36)
        destino = Path(configuracion.STORAGE_PATH) / token
        destino.mkdir(parents=True, exist_ok=True)

        transferencia = Transferencia(
            user_id       = user_id,
            token         = token,
            title         = datos.title,
            message       = datos.message,
            recipient     = datos.recipient,
            expires_at    = _expira_a_medianoche(configuracion.TRANSFER_EXPIRY_DAYS),
            max_downloads = datos.max_downloads,
            status        = EstadoTransferencia.ACTIVA.value,
        )

        archivos = await self._guardar_archivos(destino, archivos_subidos, user_id, es_original=True)
        for a in archivos:
            transferencia.archivos.append(a)

        guardado = await self.repo.crear(transferencia)
        return SalidaTransferencia.model_validate(guardado)

    async def listar_todas_activas(self) -> list[SalidaTransferencia]:
        """Todas las transferencias activas (para Sector Pacífico y Admin)."""
        transferencias = await self.repo.listar_activas()
        return [SalidaTransferencia.model_validate(t) for t in transferencias]

    async def listar_por_usuario(self, user_id: int, limite: int = 50) -> list[SalidaTransferencia]:
        limite = min(limite, 100)
        transferencias = await self.repo.listar_por_usuario(user_id, limit=limite)
        return [SalidaTransferencia.model_validate(t) for t in transferencias]

    async def obtener_publica(self, token: str) -> RespuestaTransferenciaPublica:
        transferencia = await self.repo.buscar_por_token(token)
        if not transferencia:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transferencia no encontrada.")
        return RespuestaTransferenciaPublica(
            id            = transferencia.id,
            token         = transferencia.token,
            title         = transferencia.title,
            message       = transferencia.message,
            expires_at    = transferencia.expires_at,
            downloads     = transferencia.downloads,
            max_downloads = transferencia.max_downloads,
            is_expired    = transferencia.is_expired,
            files         = transferencia.archivos,
            total_size    = transferencia.total_size,
            sender        = transferencia.usuario.full_name,
        )

    async def obtener_ruta_descarga(self, token: str, file_id: int) -> tuple[str, str]:
        """Descarga directa de un archivo puntual de la transferencia — nunca
        arma un ZIP, cada archivo se baja individualmente."""
        transferencia = await self.repo.buscar_por_token(token)
        if not transferencia:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transferencia no encontrada.")
        if transferencia.is_expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Este enlace ya no está disponible.")
        archivo = next((f for f in transferencia.archivos if f.id == file_id), None)
        if not archivo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado.")

        await self.repo.incrementar_descargas(token)
        return archivo.path, archivo.original_name

    async def obtener_ruta_preview(self, token: str, file_id: int) -> tuple[str, str | None, str]:
        transferencia = await self.repo.buscar_por_token(token)
        if not transferencia:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transferencia no encontrada.")
        if transferencia.is_expired:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Este enlace ya no está disponible.")
        archivo = next((f for f in transferencia.archivos if f.id == file_id), None)
        if not archivo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado.")
        ruta = Path(archivo.path)
        if not ruta.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo no está disponible en el servidor.")
        return str(ruta), archivo.mime_type, archivo.original_name

    async def eliminar(self, token: str, user_id: int) -> None:
        transferencia = await self.repo.buscar_por_token(token)
        if not transferencia:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transferencia no encontrada.")
        if transferencia.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para eliminar esta transferencia.",
            )

        carpeta = Path(configuracion.STORAGE_PATH) / token
        if carpeta.exists():
            shutil.rmtree(carpeta)

        await self.repo.eliminar(transferencia)
