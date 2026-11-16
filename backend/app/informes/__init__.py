"""Los archivos que arma el sistema (auditoría del 2026-11-14; hasta entonces, en core/).

- autorizacion_pdf: el PDF de la autorización (la copia de la agencia y la interna).
- estadisticas: la exportación de las estadísticas; un módulo por formato
  (estadisticas_excel, estadisticas_pdf, estadisticas_csv).
- historico_excel: la consulta histórica en Excel.
- comun, excel y pdf: lo que comparten (el archivo que se responde, fechas y
  cifras, los colores de los estados, la identidad arriba de cada hoja de Excel,
  las fuentes y el texto seguro para reportlab).

La identidad (nombres, paleta y logos) vive en core/identidad.py, con la de los
correos. Todos son CPU-bound: corren en un hilo, con turno
(infrastructure/trabajo_pesado.py).
"""
