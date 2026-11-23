# Documentación de ARGO NAVIS

Línea base técnica y funcional de ARGO NAVIS (antes «NAVIS»), módulo **Autorizaciones Marítimas** de UCVMM. Es un borrador generado desde el código fuente y está pendiente de dos revisiones: la del equipo de desarrollo y, donde se indica, la validación del área usuaria (UCVMM).

- **Versión del juego:** 0.6, borrador para revisión (08/11/2026). Trae la auditoría de rendimiento y disponibilidad de ese día: conexiones con la base de datos acotadas y con topes, respuestas 503 con motivo, chequeo de salud con la base, índices nuevos, Docker sin privilegios, la cuenta de la base de datos con lo justo, el código de cada pedido y una prueba de carga con 100 usuarios.
  - **Versiones anteriores:** la 0.5 (06/11/2026) trajo la verificación de impedimentos del puesto, los plazos de 72 horas, el horario contado con la aprobación de UCVMM y las estadísticas por día, mes y año; la 0.4 (02/11/2026), las estadísticas rediseñadas y la revisión del código; la 0.3 (30/10/2026), los puntos de la reunión de ese día.
  - El historial de cada documento dice qué cambió.
- **Versión de cada documento:** cada uno que cambia sube un número sobre el que tenía.
  - El 06 y el 08 están en la 0.6.
  - El 01, el 04 y el 09, en la 0.5. También el 00, que trae la tabla de versiones al día.
  - El 03, en la 0.4.
  - El 02, el 05 y el 07, en la 0.3.
- **Base:** rama `main`, esquema de base de datos en la revisión Alembic `e7b2d5a9c4f1`.
- **Pruebas citadas:** 220 casos del backend, 118 pruebas unitarias del frontend y 5 recorridos en el navegador, todos aprobados (08/11/2026), y una prueba de carga con 100 usuarios.
- **Capturas:**
  - Las del 01 y la 09 son de la interfaz del 30/10/2026.
  - Las de las estadísticas y la del puesto de control son del 06/11/2026.
  - Todas usan datos ficticios.

## Documentos

| N.º | Documento | Archivo |
|---|---|---|
| 00 | Inventario de procesos y mapa general de flujos | [00-Inventario-de-procesos-y-mapa-general.docx](00-Inventario-de-procesos-y-mapa-general.docx) |
| 01 | Inventario de módulos y funcionalidades | [01-Inventario-de-modulos-y-funcionalidades.docx](01-Inventario-de-modulos-y-funcionalidades.docx) |
| 02 | Flujos de procesos en BPMN 2.0 | [02-Flujos-de-procesos-BPMN.docx](02-Flujos-de-procesos-BPMN.docx) |
| 03 | Matriz de roles, perfiles y permisos | [03-Matriz-de-roles-y-permisos.docx](03-Matriz-de-roles-y-permisos.docx) |
| 04 | Catálogo de reglas de negocio y validaciones | [04-Reglas-de-negocio-y-validaciones.docx](04-Reglas-de-negocio-y-validaciones.docx) |
| 05 | Matriz de estados y transiciones | [05-Estados-y-transiciones.docx](05-Estados-y-transiciones.docx) |
| 06 | Arquitectura técnica y dependencias | [06-Arquitectura-tecnica-y-dependencias.docx](06-Arquitectura-tecnica-y-dependencias.docx) |
| 07 | Inventario de integraciones | [07-Integraciones.docx](07-Integraciones.docx) |
| 08 | Brechas, riesgos, pendientes y evidencias | [08-Brechas-riesgos-y-pendientes.docx](08-Brechas-riesgos-y-pendientes.docx) |
| 09 | Guía de funcionamiento: cómo se usa, paso a paso y por papel | [09-Guia-de-funcionamiento.docx](09-Guia-de-funcionamiento.docx) |

Para conocer el sistema sin entrar en lo técnico, empieza por el 09: explica en lenguaje sencillo qué hace cada papel (agencia, UCVMM, puesto de control y administración), con capturas. Para la línea base, se sugiere empezar por el 00 (procesos y mapa general) y terminar con el 08, que reúne los riesgos, los pendientes y la lista de puntos a validar con UCVMM.

## Manuales de usuario

Para quien usa el sistema, uno por papel: cortos, por tareas y con capturas marcadas (datos ficticios). Se reparten en PDF; el Word queda para ajustar textos. El de la agencia no nombra unidades internas del SNM, como el sistema.

| Papel | Archivo | Versión |
|---|---|---|
| Agencia naviera | [Manual-agencia-naviera.pdf](manuales/Manual-agencia-naviera.pdf) · [Word](manuales/Manual-agencia-naviera.docx) | 1.0 (19/11/2026), 5 páginas |
| UCVMM, puesto de control y supervisores | En preparación | — |

Cada documento de la línea base trae portada institucional, una página de control (datos, revisión y firmas, historial de versiones y convenciones) y un índice. Si editas un documento, actualiza el índice en Word: clic derecho sobre él → **Actualizar campo**.

## Diagramas

Los diagramas son archivos editables. Cada uno trae su imagen en PNG y SVG.

| Carpeta | Contenido | Cómo editarlos |
|---|---|---|
| [`bpmn/`](bpmn/) | Procesos en BPMN 2.0: `00` mapa general, `01` autorización de punta a punta, `02` acceso, `03` administración, `04` revisión de UCVMM, `05` finalización en el puesto, `06` vencimientos. | Camunda Modeler, [bpmn.io](https://demo.bpmn.io) o Bizagi Modeler. |
| [`diagramas/`](diagramas/) | Estados de la solicitud, arquitectura y modelo de datos, en Mermaid (`.mmd`). | Cualquier editor de texto; vista previa en [mermaid.live](https://mermaid.live). |

## Convenciones

- **Sustento:** cada hallazgo cita el archivo que lo respalda, relativo a la raíz del repositorio. En las tablas, **B:** abrevia `backend/app/` y **F:**, `frontend/src/`.
- **Estados:**
  - **Implementado:** existe en el código.
  - **Parcial:** existe una parte, por ejemplo la API sin pantalla.
  - **Pendiente:** no está construido.
  - **Fuera del sistema:** se hace a mano o en otro sistema.
  - **Validar con UCVMM:** lo debe confirmar el área usuaria.
- **Datos:** los documentos no contienen credenciales, secretos, direcciones de servidores ni datos personales reales. Las capturas de pantalla usan datos ficticios.

## Mantenimiento

- **Los Word son la fuente** (decisión del 2026-11-14). Los guiones que generaron las primeras versiones no están en el repositorio, así que los cambios se hacen en el Word. Cuando cambie el código, hay que actualizar el documento afectado y su versión en la portada.
- **Rutas que cambiaron el 2026-11-14** (auditoría del proyecto; los Word de la 0.6 citan las anteriores):

  | Antes | Ahora |
  |---|---|
  | B: `core/pdf_autorizacion.py` | B: `informes/autorizacion_pdf.py` |
  | B: `core/informe_estadisticas.py`, `informe_excel.py`, `informe_pdf.py`, `informe_csv.py` | B: `informes/estadisticas.py`, `estadisticas_excel.py`, `estadisticas_pdf.py`, `estadisticas_csv.py` |
  | B: `core/informe_historico.py` | B: `informes/historico_excel.py` |
  | B: `obtener_id_usuario_actual` y `requerir_*` (`core/security.py`, `core/permisos.py`) | B: `api/v1/dependencias.py` |
  | B: manejadores de errores y middlewares (`main.py`) | B: `api/manejadores.py`, `api/middleware.py` |
  | B: reglas de usuarios, roles y catálogos (`api/v1/admin.py`, `catalogos.py`) | B: `domain/services/usuario_service.py`, `rol_service.py`, `catalogo_service.py` |
  | F: `modulos/solicitudes/<archivo>` | F: `modulos/solicitudes/formulario/`, `expediente/`, `bandejas/`, `historico/` o `verificacion/` |
  | API: `GET /solicitudes/historico` y `/historico/exportar` | API: `POST`, con los filtros en el cuerpo |
  | Contenedores `snm_postgres`, `snm_backend`, `snm_frontend` | `argonavis_postgres`, `argonavis_backend`, `argonavis_frontend` |
- Si cambia el catálogo de trámites, también cambian el documento 04 (sección 3) y la prueba `backend/tests/test_documento_ucvmm.py`.
- Cuando UCVMM valide un punto, anota la respuesta en la lista del documento 08 (sección 4) y en la regla correspondiente del 04.
