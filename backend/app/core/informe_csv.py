"""El informe de estadísticas en CSV: un solo archivo con sus secciones.

Arriba, la identificación (sistema, institución, periodo, quién lo generó y
cuándo); después, cada sección con su título y una línea en blanco antes de
la siguiente. Para abrirlo en Excel o pasarlo a otra herramienta.

- UTF-8 con BOM (sin él, Excel muestra mal los acentos) y separado por comas,
  como lo espera Excel con la configuración regional de Panamá.
- Las cifras, sin separador de miles y con punto decimal: Excel las lee como
  números. Los porcentajes, como número con un decimal (76.6).
- Un texto que empieza con =, +, -, @, tabulador o retorno, Excel lo tomaría
  como fórmula: se le antepone un apóstrofo (OWASP, «CSV injection»). Los
  nombres de agencias, puestos y funcionarios no los escribe este módulo.
"""
import csv
import io

from app.core.horario import ZONA_PANAMA
from app.core.informe_estadisticas import (
    COLUMNAS_SERIE, DIAS_SEMANA, INSTITUCION, SECCION, SISTEMA, TITULO, UNIDADES, USO_INTERNO,
    DatosInforme, estados, indicadores, matriz_horas, ordenados_por_tramite, por_finalizar, proporcion,
    puestos_con_aprobadas, serie, texto_casilla,
)

_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _celda(valor: object) -> object:
    if valor is None:
        return ""
    if isinstance(valor, str) and valor.startswith(_FORMULA):
        return "'" + valor
    return valor


def _pct(parte: int, total: int) -> object:
    p = proporcion(parte, total)
    return "" if p is None else round(p * 100, 1)


def generar(datos: DatosInforme) -> bytes:
    e, uso = datos.estadisticas, datos.uso
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")

    def fila(*valores: object) -> None:
        escritor.writerow([_celda(v) for v in valores])

    def seccion(titulo: str, *encabezados: str) -> None:
        fila()
        fila(titulo)
        fila(*encabezados)

    fila(SISTEMA)
    fila(f"{INSTITUCION} — {SECCION}")
    fila(TITULO)
    fila("Periodo", datos.periodo)
    fila("Generado", datos.generado)
    fila(USO_INTERNO)

    seccion("Resumen del periodo", "Indicador", "Cantidad", "Porcentaje", "Base del porcentaje")
    for i in indicadores(e):
        if i.horas:
            fila(f"{i.etiqueta} (horas)", None if i.valor is None else round(i.valor, 1), "", i.base)
        else:
            porcentaje = _pct(i.parte, i.total) if i.parte is not None and i.total is not None else ""
            fila(i.etiqueta, i.valor, porcentaje, i.base)

    lista = estados(e)
    suma = sum(x.total for x in lista)
    seccion("Estado actual de las solicitudes recibidas", "Estado", "Solicitudes", "Porcentaje")
    for x in lista:
        fila(x.etiqueta, x.total, _pct(x.total, suma))

    for unidad, (columna, titulo) in UNIDADES.items():
        seccion(titulo, columna, *(nombre for _, nombre in COLUMNAS_SERIE))
        for f in serie(e, unidad):
            fila(f.periodo, *(getattr(f, clave) for clave, _ in COLUMNAS_SERIE))

    seccion("Por trámite", "Trámite", "Recibidas", "Aprobadas", "Porcentaje aprobadas", "Denegadas", "Expiradas")
    for t in ordenados_por_tramite(e):
        fila(t.nombre, t.recibidas, t.aprobadas, _pct(t.aprobadas, t.recibidas), t.negadas, t.expiradas)

    seccion("Por puesto de control (autorizaciones aprobadas)", "Puesto", "Aprobadas", "Finalizadas",
            "Por finalizar", "Expiradas")
    for p in puestos_con_aprobadas(e):
        fila(p.puesto, p.aprobadas, p.finalizadas, por_finalizar(p), p.expiradas)

    seccion("Aprobadas por día de la semana y hora (hora de Panamá)", "Día", "Hora", "Aprobadas", "Horario")
    matriz = matriz_horas(e)
    for dia in range(1, 8):
        for hora in range(24):
            if matriz[dia - 1][hora]:
                fila(DIAS_SEMANA[dia - 1], f"{hora:02d}:00 a {hora:02d}:59", matriz[dia - 1][hora],
                     texto_casilla(dia, hora))

    seccion(f"Aprobadas fuera del horario laboral ({e.horario_laboral})", "Solicitud", "Trámite", "Puesto",
            "Aprobada el", "Aprobada por")
    for o in e.operaciones_fuera_horario:
        fila(o.numero or f"#{o.id}", o.tipo_tramite, o.puesto,
             o.aprobada_en.astimezone(ZONA_PANAMA).strftime("%Y-%m-%d %H:%M"), o.aprobada_por or "")
    if e.aprobadas_fuera_horario > len(e.operaciones_fuera_horario):
        fila(f"Se muestran las {len(e.operaciones_fuera_horario)} más recientes de {e.aprobadas_fuera_horario}.")

    seccion("Uso del sistema (totales a hoy)", "Indicador", "Cantidad")
    fila("Usuarios registrados", uso.usuarios)
    fila("Usuarios activos", uso.usuarios_activos)
    fila("Agencias navieras", uso.agencias)
    fila("Documentos en expedientes", uso.documentos)
    fila("Almacenamiento usado (bytes)", uso.almacenamiento_bytes)
    seccion("Agencias con más solicitudes (desde el inicio)", "Agencia", "Solicitudes")
    for a in uso.top_agencias:
        fila(a.nombre, a.total)

    # El BOM, para que Excel la abra como UTF-8.
    return ("﻿" + salida.getvalue()).encode("utf-8")
