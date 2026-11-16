"""La identidad del SNM y de ARGO NAVIS en un solo lugar (auditoría del 2026-11-14).

La usan los correos (core/email.py), los archivos que arma el sistema
(app/informes/) y los textos que ve la agencia. Antes, cada módulo tenía su copia
de la paleta, de los logos y del nombre de la institución.

La paleta es la del tema claro de frontend/src/styles/globals.css: si cambia
allá, cambia aquí (y recalcula el contraste sobre los fondos teñidos).
"""
from pathlib import Path

SISTEMA = "ARGO NAVIS · Sistema Interno Marítimo"
# El nombre neutro que ve la agencia (2026-11-11): nunca UCVMM ni los sectores.
INSTITUCION = "Servicio Nacional de Migración"
INSTITUCION_COMPLETA = "Servicio Nacional de Migración de Panamá"   # autor de los archivos
USO_INTERNO = "Uso interno del SNM"

# Paleta del SNM (tema claro).
MARINO = "#10233F"     # títulos y encabezados de tabla
TEXTO = "#17283E"      # la tinta
GRIS = "#526176"       # textos secundarios
AMARILLO = "#F2C94C"   # la franja: solo relleno, nunca texto
BORDE = "#CAD5E1"
FONDO = "#F6F9FC"      # filas pares y recuadros
CREMA = "#FFF8D8"

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"
LOGO_SNM = RECURSOS / "logo-snm.png"
# PNG de 400 px: XlsxWriter no lee WebP (los informes).
LOGO_ARGO_NAVIS = RECURSOS / "logo-argo-navis.png"
# PNG de 141 px que se muestra a 70: Outlook de escritorio no muestra WebP (los correos).
LOGO_ARGO_NAVIS_CORREO = RECURSOS / "logo-argo-navis-correo.png"
