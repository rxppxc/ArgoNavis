"""El informe de estadísticas en Excel (.xlsx), con XlsxWriter.

- «Resumen»: la identidad (escudo del SNM, título, periodo, quién lo generó,
  logo de ARGO NAVIS y la franja amarilla), las cifras del periodo, el estado
  actual y el gráfico de la serie que se veía en pantalla.
- Una hoja por tabla: por día, por mes, por año, por trámite, por puesto, el
  mapa de horas (pintado como en la pantalla, con el horario laboral
  recuadrado), la lista de fuera del horario y el uso del sistema.

Los gráficos son nativos de Excel (se pueden copiar a un informe de Word) y
van en el color de cada estado. Las cifras son números con su formato, no
texto; las fechas, fechas de Excel en hora de Panamá. Encabezados en marino
con letra blanca, como las tablas del PDF de la autorización.
"""
import io
from typing import Any

import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from app.core.horario import ZONA_PANAMA
from app.core.informe_estadisticas import (
    AMARILLO, BORDE, COLOR_APROBADA, COLOR_EXPIRADA, COLOR_FINALIZADA, COLOR_RECIBIDAS, COLUMNAS_SERIE,
    DIAS_CORTOS, FONDO, GRIS, HORA_FIN_LABORAL, HORA_INICIO_LABORAL, INSTITUCION, LOGO_ARGO_NAVIS,
    LOGO_SNM, MARINO, NIVELES_CALOR, SERIES_DIBUJADAS, SISTEMA, TEXTO, TITULO, UNIDADES, USO_INTERNO,
    DatosInforme, color_nivel, en_horario_laboral, estados, indicadores, matriz_horas, nivel_calor,
    ordenados_por_tramite, por_finalizar, proporcion, puestos_con_aprobadas, rotulo_periodo, serie, tamano,
)

_HOJA_SERIE = {"dia": "Por día", "mes": "Por mes", "anio": "Por año"}
_ALCANCE_SERIE = {
    "dia": "Los últimos 31 días del periodo, como mucho.",
    "mes": "Los meses del periodo, hasta los últimos 12.",
    "anio": "Los años del periodo, hasta los últimos 10.",
}
_REJILLA = "#E3E9F0"
# Columna oculta con los rótulos cortos del eje de la serie («11 oct», «oct 2026»):
# con los de la tabla («Domingo 11 de octubre de 2026») el eje quedaba ilegible.
_COLUMNA_ROTULOS = 10

# Formato de cada tipo de columna de las tablas.
_TIPOS: dict[str, dict[str, Any]] = {
    "texto":      {"text_wrap": True},
    "numero":     {"num_format": "#,##0", "align": "right"},
    "porcentaje": {"num_format": "0%", "align": "right"},
    "fecha_hora": {"num_format": "dd/mm/yyyy hh:mm AM/PM", "align": "right"},
}


class _Informe:
    def __init__(self, datos: DatosInforme, salida: io.BytesIO) -> None:
        self.d = datos
        self.e = datos.estadisticas
        # Sin archivos temporales (in_memory) y sin convertir textos en fórmulas o
        # enlaces: un nombre que empiece con «=» queda como texto.
        self.libro = xlsxwriter.Workbook(salida, {
            "in_memory": True, "strings_to_formulas": False, "strings_to_urls": False,
        })
        self._formatos: dict[tuple, Any] = {}
        self.libro.set_properties({
            "title": TITULO,
            "subject": datos.periodo,
            "author": INSTITUCION,
            "company": "Servicio Nacional de Migración de Panamá",
            "category": "Estadísticas",
            "comments": f"{SISTEMA}. Generado el {datos.generado}. {USO_INTERNO}.",
        })

    # ── Formatos ─────────────────────────────────────────────────────────────

    def f(self, **props: Any):
        """Un formato, creado una sola vez por combinación (XlsxWriter no deja
        cambiar uno que ya se usó)."""
        clave = tuple(sorted(props.items()))
        if clave not in self._formatos:
            base = {"font_name": "Calibri", "font_size": 10, "font_color": TEXTO, "valign": "vcenter"}
            self._formatos[clave] = self.libro.add_format({**base, **props})
        return self._formatos[clave]

    def celda(self, fila_par: bool, **props: Any):
        """Una celda de tabla: borde fino y, en las filas pares, el fondo celeste."""
        return self.f(border=1, border_color=BORDE, bg_color=FONDO if fila_par else "#FFFFFF", **props)

    # ── Piezas comunes ───────────────────────────────────────────────────────

    def hoja(self, nombre: str, ancho: int, horizontal: bool = False) -> tuple[Worksheet, int]:
        """Una hoja con la identidad arriba; devuelve la hoja y la primera fila libre.
        La columna A es el margen con el escudo; el contenido va desde la B, en
        `ancho` columnas (el logo de ARGO NAVIS, a su derecha)."""
        h = self.libro.add_worksheet(nombre)
        h.hide_gridlines(2)
        h.set_paper(1)   # carta
        h.set_margins(left=0.5, right=0.5, top=0.75, bottom=0.75)
        h.fit_to_pages(1, 0)
        if horizontal:
            h.set_landscape()
        h.set_header(f"&L&8{TITULO}&R&8{self.d.periodo}")
        h.set_footer(f"&L&8{SISTEMA} — {INSTITUCION}. {USO_INTERNO}.&R&8Página &P de &N")
        h.set_column(0, 0, 9)
        for fila, alto in ((0, 24), (1, 16), (2, 16), (3, 16)):
            h.set_row(fila, alto)
        if LOGO_SNM.exists():
            h.insert_image(0, 0, str(LOGO_SNM), {
                "x_scale": 0.105, "y_scale": 0.105, "x_offset": 8, "y_offset": 4, "object_position": 3,
                "description": "Escudo del Servicio Nacional de Migración",
            })
        h.write_string(0, 1, TITULO, self.f(bold=True, font_size=15, font_color=MARINO))
        h.write_string(1, 1, f"{INSTITUCION} · {SISTEMA}", self.f(font_color=GRIS))
        h.write_rich_string(2, 1, self.f(bold=True, font_color=GRIS), "Periodo: ", self.f(font_color=TEXTO),
                            self.d.periodo, self.f(font_color=GRIS))
        h.write_string(3, 1, f"Generado el {self.d.generado} · {USO_INTERNO}", self.f(font_color=GRIS, italic=True))
        if LOGO_ARGO_NAVIS.exists():
            h.insert_image(0, ancho + 1, str(LOGO_ARGO_NAVIS), {
                "x_scale": 0.19, "y_scale": 0.19, "x_offset": 4, "y_offset": 2, "object_position": 3,
                "description": "Logo de ARGO NAVIS",
            })
        # La franja amarilla bajo el encabezado, como en el PDF de la autorización.
        h.set_row(4, 5)
        for col in range(ancho + 2):
            h.write_blank(4, col, None, self.f(bg_color=AMARILLO))
        return h, 6

    def titulo(self, h: Worksheet, fila: int, texto: str, nota: str | None = None) -> int:
        h.set_row(fila, 20)
        h.write_string(fila, 1, texto, self.f(bold=True, font_size=12, font_color=MARINO))
        if not nota:
            return fila + 1
        h.write_string(fila + 1, 1, nota, self.f(font_color=GRIS, italic=True, font_size=9))
        return fila + 2

    def tabla(self, h: Worksheet, fila: int, encabezados: list[str], filas: list[list[Any]], tipos: list[str],
              colores: list[str] | None = None) -> int:
        """Una tabla desde la columna B, con la fila de encabezados en `fila`. `tipos`
        da el formato de cada columna (ver _TIPOS); `colores`, una franja a la
        izquierda de cada fila (el color de su serie). Devuelve la fila siguiente,
        con una de aire."""
        h.set_row(fila, 30)
        for col, texto in enumerate(encabezados):
            h.write_string(fila, col + 1, texto, self.f(
                bold=True, font_color="#FFFFFF", bg_color=MARINO, border=1, border_color=MARINO, text_wrap=True,
                align="left" if tipos[col] == "texto" else "right"))
        if not filas:
            h.write_string(fila + 1, 1, "Sin datos en el periodo.", self.f(italic=True, font_color=GRIS))
            return fila + 3
        for i, valores in enumerate(filas, start=1):
            par = i % 2 == 0
            for col, valor in enumerate(valores):
                extra = {"left": 5, "left_color": colores[i - 1]} if colores and col == 0 else {}
                formato = self.celda(par, **_TIPOS[tipos[col]], **extra)
                if valor is None or valor == "":
                    h.write_blank(fila + i, col + 1, None, formato)
                elif tipos[col] == "fecha_hora":
                    h.write_datetime(fila + i, col + 1, valor, formato)
                elif isinstance(valor, str):
                    h.write_string(fila + i, col + 1, valor, formato)
                else:
                    h.write_number(fila + i, col + 1, valor, formato)
        return fila + len(filas) + 2

    def grafico(self, tipo: str, subtipo: str | None = None):
        """Un gráfico con el estilo de la pantalla: sin bordes, rejilla tenue y
        letras en gris (el color va en las marcas, nunca en el texto)."""
        g = self.libro.add_chart({"type": tipo, **({"subtype": subtipo} if subtipo else {})})
        g.set_title({"none": True})   # el título va en la celda de arriba (Excel ponía el de la serie)
        g.set_chartarea({"border": {"none": True}})
        g.set_plotarea({"border": {"none": True}})
        g.set_legend({"position": "top", "font": {"color": GRIS, "size": 9}})
        valores = {"num_font": {"color": GRIS, "size": 8}, "line": {"none": True},
                   "major_gridlines": {"visible": True, "line": {"color": _REJILLA, "width": 0.75}}}
        categorias = {"num_font": {"color": TEXTO, "size": 8}, "line": {"color": BORDE}}
        if tipo == "bar":   # barras horizontales: las categorías van en el eje vertical
            g.set_x_axis(valores)
            g.set_y_axis({**categorias, "reverse": True})   # la primera fila, arriba
        else:
            g.set_y_axis(valores)
            g.set_x_axis(categorias)
        return g

    def barras(self, h: Worksheet, fila_encabezado: int, n: int, columna_valor: int, nombre: str, color: str,
               ancho: int):
        """Barras horizontales de una columna de la tabla (con la cifra en la punta)."""
        g = self.grafico("bar")
        g.add_series({
            "name": nombre,
            "categories": [h.name, fila_encabezado + 1, 1, fila_encabezado + n, 1],
            "values": [h.name, fila_encabezado + 1, columna_valor, fila_encabezado + n, columna_valor],
            "fill": {"color": color}, "border": {"none": True}, "gap": 70,
            "data_labels": {"value": True, "font": {"color": TEXTO, "size": 8}},
        })
        g.set_legend({"none": True})
        g.set_size({"width": ancho, "height": 60 + 32 * n})
        return g

    # ── Hojas ────────────────────────────────────────────────────────────────

    def resumen(self) -> tuple[Worksheet, int]:
        """La primera hoja. Devuelve dónde va el gráfico de la serie, que se
        inserta después de armar su hoja."""
        e = self.e
        h, fila = self.hoja("Resumen", ancho=7)
        h.set_tab_color(AMARILLO)
        h.set_column(1, 1, 34)
        h.set_column(2, 3, 12)
        h.set_column(4, 4, 32)
        h.set_column(5, 8, 12)

        fila = self.titulo(h, fila, "Cifras del periodo")
        lista = indicadores(e)
        fila = self.tabla(
            h, fila, ["Indicador", "Cantidad", "%", "Base del porcentaje"],
            [[i.etiqueta, i.texto if i.horas else i.valor,
              proporcion(i.parte, i.total) if i.total is not None and i.parte is not None else None, i.base]
             for i in lista],
            ["texto", "numero", "porcentaje", "texto"], colores=[i.color for i in lista])

        # Estado actual: tabla y barras, cada estado en su color.
        lista_estados = estados(e)
        suma = sum(x.total for x in lista_estados)
        fila = self.titulo(h, fila, "Estado actual de las solicitudes recibidas",
                           "En qué estado están hoy las que llegaron en el periodo.")
        encabezado = fila
        fila = self.tabla(h, fila, ["Estado", "Solicitudes", "%"],
                          [[x.etiqueta, x.total, proporcion(x.total, suma)] for x in lista_estados],
                          ["texto", "numero", "porcentaje"], colores=[x.color for x in lista_estados])
        if suma:
            g = self.grafico("bar")
            g.add_series({
                "name": "Solicitudes",
                "categories": ["Resumen", encabezado + 1, 1, encabezado + len(lista_estados), 1],
                "values": ["Resumen", encabezado + 1, 2, encabezado + len(lista_estados), 2],
                "points": [{"fill": {"color": x.color}, "border": {"none": True}} for x in lista_estados],
                "data_labels": {"value": True, "font": {"color": TEXTO, "size": 8}},
                "gap": 60,
            })
            g.set_legend({"none": True})
            g.set_size({"width": 430, "height": 230})
            h.insert_chart(encabezado, 5, g, {"x_offset": 12, "object_position": 1})

        titulo = UNIDADES[self.d.unidad][1]
        fila = self.titulo(h, max(fila, encabezado + 13), titulo,
                           f"Cada cifra cuenta en la fecha en que ocurrió. Los datos, en la hoja «{_HOJA_SERIE[self.d.unidad]}».")
        return h, fila

    def grafico_serie(self, unidad: str, primera: int, n: int):
        """Columnas de la serie: recibidas, aprobadas y finalizadas, como en la pantalla."""
        hoja = _HOJA_SERIE[unidad]
        g = self.grafico("column")
        g.show_hidden_data()   # los rótulos cortos están en una columna oculta
        claves = [c for c, _ in COLUMNAS_SERIE]
        for clave, nombre, color in SERIES_DIBUJADAS:
            col = 2 + claves.index(clave)
            g.add_series({
                "name": nombre,
                "categories": [hoja, primera, _COLUMNA_ROTULOS, primera + n - 1, _COLUMNA_ROTULOS],
                "values": [hoja, primera, col, primera + n - 1, col],
                "fill": {"color": color}, "border": {"none": True}, "gap": 80, "overlap": -8,
            })
        g.set_size({"width": 860, "height": 300})
        return g

    def hoja_serie(self, unidad: str) -> tuple[int, int, bool]:
        """Devuelve la primera fila de datos, cuántas hay y si hubo movimiento."""
        columna, titulo = UNIDADES[unidad]
        h, fila = self.hoja(_HOJA_SERIE[unidad], ancho=7, horizontal=True)
        h.set_column(1, 1, 30 if unidad == "dia" else 18)
        h.set_column(2, 7, 12)
        fila = self.titulo(h, fila, titulo, f"{_ALCANCE_SERIE[unidad]} Cada cifra cuenta en la fecha en que ocurrió.")
        filas = serie(self.e, unidad)
        encabezado = fila
        siguiente = self.tabla(
            h, fila, [columna, *(nombre for _, nombre in COLUMNAS_SERIE)],
            [[rotulo_periodo(f.periodo)[2], *(getattr(f, clave) for clave, _ in COLUMNAS_SERIE)] for f in filas],
            ["texto", *["numero"] * len(COLUMNAS_SERIE)])
        h.set_column(_COLUMNA_ROTULOS, _COLUMNA_ROTULOS, None, None, {"hidden": True})
        for i, f in enumerate(filas):
            arriba, abajo, _ = rotulo_periodo(f.periodo)
            h.write_string(encabezado + 1 + i, _COLUMNA_ROTULOS, f"{arriba} {abajo}".strip())
        movimiento = any(f.recibidas or f.aprobadas or f.finalizadas for f in filas)
        if movimiento:
            h.insert_chart(siguiente, 1, self.grafico_serie(unidad, encabezado + 1, len(filas)), {"object_position": 1})
        return encabezado + 1, len(filas), movimiento

    def hoja_tramites(self) -> None:
        h, fila = self.hoja("Por trámite", ancho=6)
        h.set_column(1, 1, 44)
        h.set_column(2, 6, 12)
        fila = self.titulo(h, fila, "Por trámite", "Solicitudes recibidas en el periodo, por tipo de trámite.")
        tramites = ordenados_por_tramite(self.e)
        encabezado = fila
        fila = self.tabla(h, fila, ["Trámite", "Recibidas", "Aprobadas", "% aprobadas", "Denegadas", "Expiradas"],
                          [[t.nombre, t.recibidas, t.aprobadas, proporcion(t.aprobadas, t.recibidas), t.negadas,
                            t.expiradas] for t in tramites],
                          ["texto", "numero", "numero", "porcentaje", "numero", "numero"])
        if tramites:
            h.insert_chart(fila, 1, self.barras(h, encabezado, len(tramites), 2, "Recibidas", COLOR_RECIBIDAS, 720),
                           {"object_position": 1})

    def hoja_puestos(self) -> None:
        h, fila = self.hoja("Por puesto", ancho=5)
        h.set_column(1, 1, 40)
        h.set_column(2, 5, 13)
        fila = self.titulo(h, fila, "Por puesto de control",
                           "Las autorizaciones aprobadas para cada puesto y en qué terminaron.")
        puestos = puestos_con_aprobadas(self.e)
        encabezado = fila
        fila = self.tabla(h, fila, ["Puesto", "Aprobadas", "Finalizadas", "Por finalizar", "Expiradas"],
                          [[p.puesto, p.aprobadas, p.finalizadas, por_finalizar(p), p.expiradas] for p in puestos],
                          ["texto", "numero", "numero", "numero", "numero"])
        if puestos:
            g = self.grafico("bar", "stacked")
            for col, nombre, color in ((3, "Finalizadas", COLOR_FINALIZADA), (4, "Por finalizar", COLOR_APROBADA),
                                       (5, "Expiradas", COLOR_EXPIRADA)):
                g.add_series({
                    "name": nombre,
                    "categories": [h.name, encabezado + 1, 1, encabezado + len(puestos), 1],
                    "values": [h.name, encabezado + 1, col, encabezado + len(puestos), col],
                    # 1 px del fondo entre segmentos, como los 2 px de la pantalla.
                    "fill": {"color": color}, "border": {"color": "#FFFFFF", "width": 1}, "gap": 70,
                })
            g.set_size({"width": 720, "height": 80 + 32 * len(puestos)})
            h.insert_chart(fila, 1, g, {"object_position": 1})

    def hoja_horas(self) -> None:
        e = self.e
        h, fila = self.hoja("Horas de aprobación", ancho=24, horizontal=True)
        h.set_column(1, 1, 12)
        h.set_column(2, 25, 4.3)
        fila = self.titulo(h, fila, "Hora de aprobación de UCVMM",
                           f"Aprobadas por día y hora, en hora de Panamá. Recuadro: horario laboral "
                           f"({e.horario_laboral}; desde las 15:01 es fuera).")
        h.write_string(fila, 1, f"Fuera del horario: {e.aprobadas_fuera_horario:,} de {e.aprobadas:,} aprobadas.",
                       self.f(bold=True))
        fila += 2
        matriz = matriz_horas(e)
        maximo = max(max(f) for f in matriz)
        for hora in range(24):
            h.write_string(fila, hora + 2, f"{hora:02d}", self.f(bold=True, font_color=GRIS, font_size=8, align="center"))
        for dia in range(1, 8):
            r = fila + dia
            h.set_row(r, 20)
            h.write_string(r, 1, DIAS_CORTOS[dia - 1], self.f(bold=True, font_color=GRIS))
            for hora in range(24):
                total = matriz[dia - 1][hora]
                nivel = nivel_calor(total, maximo)
                # El recuadro del horario laboral: borde grueso en el contorno (lunes a viernes, 07 a 14).
                borde: dict[str, Any] = {}
                if en_horario_laboral(dia, hora):
                    if dia == 1:
                        borde |= {"top": 2, "top_color": TEXTO}
                    if dia == 5:
                        borde |= {"bottom": 2, "bottom_color": TEXTO}
                    if hora == HORA_INICIO_LABORAL:
                        borde |= {"left": 2, "left_color": TEXTO}
                    if hora == HORA_FIN_LABORAL - 1:
                        borde |= {"right": 2, "right_color": TEXTO}
                formato = self.f(bg_color=color_nivel(nivel), font_color="#FFFFFF" if nivel >= 4 else TEXTO,
                                 font_size=8, align="center", **borde)
                if total:
                    h.write_number(r, hora + 2, total, formato)
                else:
                    h.write_blank(r, hora + 2, None, formato)
        fila += 9
        h.write_string(fila, 1, "Menos", self.f(font_color=GRIS, font_size=8, align="right"))
        for n in range(NIVELES_CALOR + 1):
            h.write_blank(fila, n + 2, None, self.f(bg_color=color_nivel(n)))
        h.write_string(fila, NIVELES_CALOR + 3, "Más", self.f(font_color=GRIS, font_size=8))
        h.write_blank(fila, NIVELES_CALOR + 6, None, self.f(border=2, border_color=TEXTO))
        h.write_string(fila, NIVELES_CALOR + 7, "Horario laboral", self.f(font_color=GRIS, font_size=8))

    def hoja_fuera(self) -> None:
        e = self.e
        h, fila = self.hoja("Fuera del horario", ancho=5)
        for col, ancho in ((1, 18), (2, 34), (3, 26), (4, 20), (5, 28)):
            h.set_column(col, col, ancho)
        lista = e.operaciones_fuera_horario
        nota = f"Horario laboral: {e.horario_laboral}. Cuenta la hora de la aprobación de UCVMM."
        if e.aprobadas_fuera_horario > len(lista):
            nota += f" Se muestran las {len(lista)} más recientes de {e.aprobadas_fuera_horario:,}."
        fila = self.titulo(h, fila, "Autorizaciones aprobadas fuera del horario", nota)
        self.tabla(h, fila, ["Solicitud", "Trámite", "Puesto", "Aprobada el", "Aprobada por"],
                   [[o.numero or f"#{o.id}", o.tipo_tramite, o.puesto,
                     o.aprobada_en.astimezone(ZONA_PANAMA).replace(tzinfo=None), o.aprobada_por or "—"]
                    for o in lista],
                   ["texto", "texto", "texto", "fecha_hora", "texto"])

    def hoja_uso(self) -> None:
        uso = self.d.uso
        h, fila = self.hoja("Uso del sistema", ancho=5)
        h.set_column(1, 1, 40)
        h.set_column(2, 2, 16)
        fila = self.titulo(h, fila, "Uso del sistema", "Totales a hoy: no dependen del periodo.")
        fila = self.tabla(h, fila, ["Indicador", "Cantidad"], [
            ["Usuarios registrados", uso.usuarios],
            ["Usuarios activos", uso.usuarios_activos],
            ["Agencias navieras", uso.agencias],
            ["Documentos en expedientes", uso.documentos],
            ["Almacenamiento usado", tamano(uso.almacenamiento_bytes)],
        ], ["texto", "numero"])
        fila = self.titulo(h, fila, "Agencias con más solicitudes", "Las cinco con más solicitudes, desde el inicio.")
        encabezado = fila
        fila = self.tabla(h, fila, ["Agencia", "Solicitudes"], [[a.nombre, a.total] for a in uso.top_agencias],
                          ["texto", "numero"])
        if uso.top_agencias:
            h.insert_chart(fila, 1, self.barras(h, encabezado, len(uso.top_agencias), 2, "Solicitudes",
                                                COLOR_RECIBIDAS, 560), {"object_position": 1})

    def generar(self) -> None:
        hoja_resumen, fila_grafico = self.resumen()
        series = {unidad: self.hoja_serie(unidad) for unidad in UNIDADES}
        primera, n, movimiento = series[self.d.unidad]
        if movimiento:
            hoja_resumen.insert_chart(fila_grafico, 1, self.grafico_serie(self.d.unidad, primera, n),
                                      {"y_offset": 4, "object_position": 1})
        else:
            hoja_resumen.write_string(fila_grafico, 1, "Sin movimiento en el periodo.",
                                      self.f(italic=True, font_color=GRIS))
        self.hoja_tramites()
        self.hoja_puestos()
        self.hoja_horas()
        self.hoja_fuera()
        self.hoja_uso()
        self.libro.close()


def generar(datos: DatosInforme) -> bytes:
    salida = io.BytesIO()
    _Informe(datos, salida).generar()
    return salida.getvalue()
