# Consola web de Vigilia

La consola de escritorio está implementada en inglés con HTML, CSS y módulos JavaScript nativos. FastAPI sirve `/ui/` desde `src/vigilia/adapters/http/ui/`; los assets se incluyen al instalar el paquete y en Docker. No necesita npm ni un proceso frontend adicional.

## Acceso y navegación

Al abrir la consola se introduce `VIGILIA_API_TOKEN`. El token permanece en memoria y se envía como Bearer a la API; recargar o bloquear la sesión lo elimina. Las rutas internas usan el hash, por ejemplo `/ui/#/incidents/{id}`. Datos externos se insertan como texto y los enlaces solo aceptan HTTP/HTTPS.

| Vista | Comportamiento |
| --- | --- |
| Overview | Totales y actividad reciente obtenidos de la API |
| Incidents | Lista, filtros locales, detalle y línea temporal |
| Investigación | Solicitud idempotente, estado, resultado, evidencias e intentos |
| Alerts | Eventos paginados y filtros de servicio/estado |
| Knowledge | Metadatos paginados, carga de texto o `.md`/`.txt`, reemplazo y borrado |

Los estados `queued`, `running` y `retry_wait` se consultan cada tres segundos. El polling se detiene al completar/fallar, salir de la vista o esconder la pestaña. El coste mostrado es una estimación. Los resultados históricos `legacy_report.v1` se muestran como JSON para conservar acceso a su contenido.

La API requiere RAG para indexar documentos; el listado funciona también con RAG apagado. Un documento se reemplaza usando el mismo servicio y fuente en el entorno configurado. Las investigaciones previas conservan sus evidencias recuperadas.

## Límites actuales

- El listado de incidentes no está paginado y sus filtros se aplican en el navegador.
- La interfaz se ha diseñado para escritorio; falta validar un diseño móvil.
- Hay una única credencial Bearer; no existen usuarios ni roles.
- No hay WebSocket/SSE, acciones de remediación ni edición de incidentes.
- La API no expone el texto completo de los documentos almacenados.
- Falta ampliar las pruebas de interfaz, accesibilidad y estados de error.

El flujo de validación reproducible está en [README](../README.md) y las prioridades pendientes en [el roadmap](../VIGILIA_ROADMAP.md).
