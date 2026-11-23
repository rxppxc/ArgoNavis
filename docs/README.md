# Documentación de ARGO NAVIS

Línea base técnica y funcional de ARGO NAVIS (antes «NAVIS»), módulo **Autorizaciones Marítimas** de UCVMM. Es un borrador generado desde el código fuente y está pendiente de dos revisiones: la del equipo de desarrollo y, donde se indica, la validación del área usuaria (UCVMM).

- **Versión del juego:** 0.7, borrador para revisión (23/11/2026). Trae lo del 10 al 22/11/2026:
  - los sectores de UCVMM y los supervisores;
  - los cambios de los trámites: cambio de puerto, rango Pasajero, visas, operación de Técnico y días del sellado;
  - el recargo fuera del horario y su boleta;
  - la consulta histórica y el historial completo;
  - el PDF por el QR;
  - los contenedores endurecidos, HTTPS listo para activar, PostgreSQL 18 elegible, la vigilancia y los respaldos con retención de años;
  - las dependencias al día, con los tipos y la cobertura en la CI.
  - **Versiones anteriores:** la 0.6 (08/11/2026) trajo la auditoría de rendimiento y disponibilidad; la 0.5 (06/11/2026), la verificación de impedimentos del puesto, los plazos de 72 horas, el horario contado con la aprobación de UCVMM y las estadísticas por día, mes y año; la 0.4 (02/11/2026), las estadísticas rediseñadas y la revisión del código; la 0.3 (30/10/2026), los puntos de la reunión de ese día.
  - El historial de cada documento dice qué cambió.
- **Versión de cada documento:** cada uno que cambia sube un número sobre el que tenía. Esta vez cambiaron todos.
  - El 06 y el 08 están en la 0.7.
  - El 00, el 01, el 04 y el 09, en la 0.6.
  - El 03, en la 0.5.
  - El 02, el 05 y el 07, en la 0.4.
- **Base:** rama `main`, esquema de base de datos en la revisión Alembic `d7f3b0c5e849`.
- **Pruebas citadas (23/11/2026):**
  - backend: 644 casos, 643 aprobados y 1 omitido en Windows, que la CI corre en Linux; cobertura del 95,4 % y `mypy` sin avisos;
  - frontend: 266 pruebas unitarias y 15 recorridos en el navegador, todos aprobados;
  - la prueba de carga con 100 usuarios es del 08/11/2026.
- **Capturas:** las del 01 y la 09 son del 23/11/2026, con la interfaz de hoy, tomadas contra una base de datos temporal de prueba (sin correos). Todas usan datos ficticios.

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

Para conocer el sistema sin entrar en lo técnico, empieza por el 09: explica en lenguaje sencillo qué hace cada papel (agencia, UCVMM, puesto de control, supervisión y administración), con capturas. Para la línea base, se sugiere empezar por el 00 (procesos y mapa general) y terminar con el 08, que reúne los riesgos, los pendientes y la lista de puntos a validar con UCVMM.

## Manuales de usuario

Para quien usa el sistema, uno por papel (los dos supervisores, en uno): cortos, por tareas y con capturas marcadas (datos ficticios). Llevan la portada, el encabezado y el pie del formato de manuales de la DTI. Se reparten en PDF; el Word queda para ajustar textos. El de la agencia no nombra unidades internas del SNM, como el sistema.

| Papel | Archivo | Versión |
|---|---|---|
| Agencia naviera | [Manual-agencia-naviera.pdf](manuales/Manual-agencia-naviera.pdf) · [Word](manuales/Manual-agencia-naviera.docx) | 1.1 (23/11/2026), 7 páginas |
| UCVMM | [Manual-UCVMM.pdf](manuales/Manual-UCVMM.pdf) · [Word](manuales/Manual-UCVMM.docx) | 1.0 (23/11/2026), 10 páginas |
| Puesto de control | [Manual-puesto-de-control.pdf](manuales/Manual-puesto-de-control.pdf) · [Word](manuales/Manual-puesto-de-control.docx) | 1.0 (23/11/2026), 6 páginas |
| Supervisores (de sector y general) | [Manual-supervisores.pdf](manuales/Manual-supervisores.pdf) · [Word](manuales/Manual-supervisores.docx) | 1.0 (23/11/2026), 8 páginas |

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

- **Los Word son la fuente** (decisión del 2026-11-14). Los guiones que generan los documentos no están en el repositorio, así que los cambios se hacen en el Word. Cuando cambie el código, hay que actualizar el documento afectado y su versión en la portada.
  - La 0.7 se volvió a generar con esos guiones, que siguen fuera del repositorio. Antes se comprobó que los Word de la 0.6 no tenían cambios a mano: el texto regenerado era idéntico.
  - Ya cita las rutas nuevas de la auditoría del 2026-11-14 (`informes/`, `api/v1/dependencias.py`, las carpetas de `modulos/solicitudes/` y los contenedores `argonavis_*`).
- **Diagramas:** el 2026-11-23 se pusieron al día los BPMN 00, 01, 03, 04 y 05, y los Mermaid de arquitectura y modelo de datos. Si editas un `.bpmn` o un `.mmd`, vuelve a exportar su PNG y su SVG.
- **Manuales de usuario:** también se generan con guiones fuera del repositorio, con capturas tomadas contra la pila del E2E. Si cambia una pantalla que muestran, hay que cambiar el texto en el Word y, si la captura ya no se parece, tomarla de nuevo.
- Si cambia el catálogo de trámites, también cambian el documento 04 (sección 3) y la prueba `backend/tests/test_documento_ucvmm.py`.
- Cuando UCVMM valide un punto, anota la respuesta en la lista del documento 08 (sección 4) y en la regla correspondiente del 04.
