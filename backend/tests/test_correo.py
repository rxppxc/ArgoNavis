"""Correo de los avisos (diseño "pase marítimo"): asunto, partes del mensaje,
logo incrustado y escape de lo que escribe el usuario. No envía nada."""
from app.core.email import Aviso, construir_mensaje
from app.domain.services.notificacion_service import _vista_previa

CAMPOS = [
    ("Buque", "ISTMO EXPRESS"), ("IMO", "9074729"), ("Trámite", "Embarque"),
    ("Puesto", "Puerto de Balboa"), ("Operación", "15/10/2026"), ("Tripulantes", "1"),
    ("Agencia naviera", "Agencia Marítima del Istmo"),
]


def _aviso(**cambios) -> Aviso:
    datos = dict(
        destinatarios=["agencia@prueba.local"], numero="AM-2026-000011", estado="Devuelta a corrección",
        titulo="La solicitud necesita correcciones", intro="UCVMM revisó la solicitud.",
        vista_previa="Motivo: libreta ilegible · corrige antes del 17/10 11:59 PM", campos=CAMPOS,
        destacado="Motivo: libreta ilegible", tono="rojo",
        boton_texto="Corregir solicitud", boton_url="https://argonavis.prueba/solicitudes/11/corregir",
    )
    datos.update(cambios)
    return Aviso(**datos)


def _partes(mensaje):
    texto = mensaje.get_body(preferencelist=("plain",)).get_content()
    html = mensaje.get_body(preferencelist=("html",)).get_content()
    imagenes = [p for p in mensaje.walk() if p.get_content_type() == "image/png"]
    return texto, html, imagenes


def test_asunto_con_codigo_y_estado():
    mensaje = construir_mensaje(_aviso(), ["agencia@prueba.local"])
    assert mensaje["Subject"] == "Autorizaciones Marítimas · AM-2026-000011 · Devuelta a corrección"
    assert mensaje["Auto-Submitted"] == "auto-generated"


def test_texto_plano_html_y_logo_incrustado():
    mensaje = construir_mensaje(_aviso(), ["agencia@prueba.local"])
    assert mensaje.get_content_type() == "multipart/alternative"
    texto, html, imagenes = _partes(mensaje)
    assert "Buque: ISTMO EXPRESS" in texto and "Corregir solicitud: https://argonavis.prueba/solicitudes/11/corregir" in texto
    assert len(imagenes) == 1 and imagenes[0]["Content-ID"] == "<logo-argo-navis@argonavis.snm>"
    assert 'src="cid:logo-argo-navis@argonavis.snm"' in html, "el HTML usa el logo incrustado, no una URL externa"
    assert "Motivo: libreta ilegible · corrige antes del" in html, "lleva la vista previa para la bandeja"
    assert 'colspan="3"' in html and "Agencia Marítima del Istmo" in html, "la agencia ocupa la última fila"


def test_campos_vacios_no_se_muestran():
    sin_buque = [(e, "" if e in ("Buque", "IMO") else v) for e, v in CAMPOS]
    _, html, _ = _partes(construir_mensaje(_aviso(campos=sin_buque), ["x@prueba.local"]))
    assert ">Buque<" not in html and ">IMO<" not in html and ">Trámite<" in html


def test_contenido_del_usuario_se_escapa():
    aviso = _aviso(destacado='Motivo: <script>alert(1)</script> <a href="http://malo">aquí</a>',
                   intro="Agencia <b>X</b>", vista_previa="<img src=x onerror=alert(1)>")
    _, html, _ = _partes(construir_mensaje(aviso, ["x@prueba.local"]))
    assert "<script>" not in html and 'href="http://malo"' not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html and "Agencia &lt;b&gt;X&lt;/b&gt;" in html
    assert "<b>Motivo:</b> &lt;script&gt;" in html, "solo la etiqueta propia va en negrita"


def test_asunto_sin_saltos_de_linea():
    mensaje = construir_mensaje(_aviso(estado="Negada\r\nBcc: alguien@fuera.com"), ["x@prueba.local"])
    assert "\n" not in mensaje["Subject"] and mensaje["Bcc"] is None


def test_vista_previa_en_una_linea_y_corta():
    assert _vista_previa("Motivo: la libreta\nestá ilegible", None, "", "corrige antes del 17/10") == \
        "Motivo: la libreta está ilegible · corrige antes del 17/10"
    larga = _vista_previa("x" * 400)
    assert len(larga) == 150 and larga.endswith("…")
