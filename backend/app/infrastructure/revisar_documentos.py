"""¿Siguen en el disco los archivos de las solicitudes, y son los mismos? (2026-11-22)

Las solicitudes se consultan años después y un archivo que se pierde o se daña sin que nadie
lo note, al final, tampoco está en los respaldos. Esto compara cada documento registrado
(vigente o retirado) y cada autorización emitida con su archivo: que esté y que mida lo mismo.
Y cada día relee los de un día del mes y comprueba su huella: en 31 días, todos. Nombra los
que no están como deben, para recuperarlos del respaldo. No cambia nada.

    docker exec argonavis_backend python -m app.infrastructure.revisar_documentos

Lo corre verificar-despliegue.sh después de cada despliegue y, con vigilar.py, cada mañana.
Termina con 0 si están todos.
"""
import asyncio
import os
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.horario import ZONA_PANAMA
# Todos los modelos que el ORM relaciona con la solicitud (no se carga app.main).
from app.domain.models import catalogo, rol, tramite, user  # noqa: F401
from app.domain.models.solicitud import DocumentoEmitido, DocumentoSolicitud
from app.domain.repositories.solicitud_repository import RepositorioSolicitud
from app.infrastructure import almacenamiento
from app.infrastructure.database import SesionLocal, motor_bd

LOTE = 5000       # archivos por consulta
NOMBRADOS = 10    # en el resumen, los primeros; el resto, contado
DIAS = 31         # en cuántos días se relee todo
_QUE_ES: dict[type[DocumentoSolicitud] | type[DocumentoEmitido], str] = {
    DocumentoSolicitud: "documento", DocumentoEmitido: "autorización emitida"}


@dataclass
class Revision:
    total:     int                                          # archivos registrados
    releidos:  int = 0                                      # a cuántos se les comprobó la huella hoy
    problemas: list[str] = field(default_factory=list)      # «AM-2026-000123: falta solicitud-9/ab.pdf (documento 45)»

    def resumen(self) -> str:
        if not self.problemas:
            if self.total == 0:
                return "Sin archivos registrados todavía"
            huella = f"; hoy se releyeron {self.releidos:,} y son los originales" if self.releidos else ""
            if self.total == 1:
                return f"1 archivo registrado, en el disco y con su tamaño{huella}"
            return f"{self.total:,} archivos registrados, todos en el disco y con su tamaño{huella}"
        lineas = [f"{len(self.problemas):,} de {self.total:,} archivos no están como deben. "
                  "Recupéralos del último respaldo (README → Respaldos):"]
        lineas += [f"  {p}" for p in self.problemas[:NOMBRADOS]]
        if len(self.problemas) > NOMBRADOS:
            lineas.append(f"  y {len(self.problemas) - NOMBRADOS} más")
        return "\n".join(lineas)


def _toca_releer(archivo, dia: int) -> bool:
    return bool(archivo.sha256) and archivo.id % DIAS == dia % DIAS


def _mirar(archivos: Iterable, dia: int) -> dict[int, str]:
    """{id: qué le pasa} de los que no están como deben. Corre en un hilo: mira el disco.
    Sin resolver cada ruta (como `ruta_segura`, que sirve archivos): son cientos de miles y
    aquí no se entrega ninguno. Las que salen de la carpeta cuentan como faltantes."""
    raiz = almacenamiento.raiz_documentos()
    problemas = {}
    for a in archivos:
        relativa = Path(a.ruta)
        if relativa.is_absolute() or relativa.drive or ".." in relativa.parts:
            problemas[a.id] = f"falta {a.ruta}"
            continue
        try:
            datos = os.stat(raiz / relativa)
            if not stat.S_ISREG(datos.st_mode):
                problemas[a.id] = f"falta {a.ruta}"
            elif datos.st_size != a.tamano:
                problemas[a.id] = f"{a.ruta} mide {datos.st_size} bytes y debía medir {a.tamano}"
            elif _toca_releer(a, dia) and almacenamiento.huella_de(raiz / relativa) != a.sha256:
                problemas[a.id] = f"{a.ruta} no es el original: no coincide con su huella"
        except OSError:   # no está, o no se puede leer: es lo que se busca
            problemas[a.id] = f"falta {a.ruta}"
    return problemas


async def _registrados(modelo: type, ids: list[int]) -> list:
    async with SesionLocal() as sesion:
        return await RepositorioSolicitud(sesion).archivos_con_su_solicitud(modelo, ids)


async def revisar(dia: int | None = None) -> Revision:
    """`dia`: el del mes (hoy, en hora de Panamá), que dice cuáles se releen."""
    dia = datetime.now(ZONA_PANAMA).day if dia is None else dia
    revision = Revision(total=0)
    for modelo, que_es in _QUE_ES.items():
        sospechosos: list[int] = []   # los id de los que hay que volver a mirar
        ultimo = 0
        while True:
            async with SesionLocal() as sesion:
                archivos = await RepositorioSolicitud(sesion).archivos_desde(modelo, ultimo, LOTE)
            if not archivos:
                break
            ultimo = archivos[-1].id
            revision.total += len(archivos)
            revision.releidos += sum(_toca_releer(a, dia) for a in archivos)
            sospechosos += await asyncio.to_thread(_mirar, archivos, dia)
        # Otra mirada, por si algo cambió entre leer la lista y mirar el disco.
        if sospechosos:
            registrados = await _registrados(modelo, sospechosos)
            problemas = await asyncio.to_thread(_mirar, registrados, dia)
            revision.problemas += [f"{a.numero or f'Solicitud {a.solicitud_id}'}: {problemas[a.id]} ({que_es} {a.id})"
                                   for a in registrados if a.id in problemas]
    return revision


async def _principal() -> int:
    try:
        revision = await revisar()
    finally:
        await motor_bd.dispose()
    print(revision.resumen())
    return 1 if revision.problemas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_principal()))
