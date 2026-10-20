# Documentación de ARGO NAVIS

Línea base técnica y funcional de ARGO NAVIS (antes «NAVIS»), módulo **Autorizaciones Marítimas** de UCVMM. Es un borrador generado desde el código fuente y está pendiente de dos revisiones: la del equipo de desarrollo y, donde se indica, la validación del área usuaria (UCVMM).

- **Versión:** 0.1, borrador para revisión (20/10/2026).
- **Base:** rama `main`, esquema de base de datos en la revisión Alembic `a3d9c6e1f584`.
- **Pruebas citadas:** 113 casos del backend aprobados (19/10/2026).

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

Se sugiere empezar por el 00 (procesos y mapa general) y terminar con el 08, que reúne los riesgos, los pendientes y la lista de puntos a validar con UCVMM.

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

- Los Word son la versión editable. Cuando cambie el código, hay que actualizar el documento afectado y su versión en la portada.
- Si cambia el catálogo de trámites, también cambian el documento 04 (sección 3) y la prueba `backend/tests/test_documento_ucvmm.py`.
- Cuando UCVMM valide un punto, anota la respuesta en la lista del documento 08 (sección 4) y en la regla correspondiente del 04.
