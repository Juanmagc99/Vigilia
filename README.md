# Vigilia

Vigilia recibe alertas de Grafana, las agrupa en incidentes y permite investigarlos con evidencias auditables. Usa PostgreSQL como fuente de verdad, Redpanda para el trabajo asíncrono y ofrece una consola web en inglés.

El análisis funciona con un simulador local o con un modelo configurado mediante LiteLLM. RAG permite añadir runbooks y otra documentación operacional a las investigaciones.

## Arranque local

Requisitos: Docker con Compose, Python 3.13, [uv](https://docs.astral.sh/uv/) y Make.

```powershell
Copy-Item .env.example .env
# Edita .env y cambia los secretos de desarrollo.
uv sync --locked
make dev-start
```

La primera puesta en marcha crea la base de datos y los topics. Para probar sin llamadas a proveedores, configura `VIGILIA_INVESTIGATION_ANALYZER=simulated` y `VIGILIA_RAG_ENABLED=false` en `.env`.

- Consola: <http://localhost:8000/ui/>
- API y OpenAPI: <http://localhost:8000/docs>
- Grafana local: <http://localhost:3000> (`admin` / `admin`)

La consola solicita `VIGILIA_API_TOKEN`; lo mantiene en memoria hasta recargar la página. Para enviar alertas sintéticas:

```powershell
uv run --locked python scripts/send_grafana_alert.py --service payments-api --status firing --severity critical --alert-name HighCPU
```

## Comandos útiles

| Comando | Acción |
| --- | --- |
| `make help` | Ver todos los comandos |
| `make dev-start` | Construir y arrancar el entorno |
| `make dev-status` | Ver el estado de los servicios |
| `make dev-logs` | Seguir los logs locales |
| `make dev-rebuild` | Reconstruir la aplicación y reiniciarla |
| `make dev-stop` | Parar servicios conservando los datos |
| `make smoke` | Ejecutar el flujo básico contra el stack local |
| `make seed-knowledge` | Indexar los runbooks de ejemplo; requiere embeddings |

## Configuración y documentación

La configuración vive en `.env`; empieza por [.env.example](.env.example). La generación real y la indexación RAG pueden consumir cuota del proveedor. Configúralas solo cuando quieras probarlas.

- [Arquitectura](docs/architecture.md) y [decisiones](docs/decisions/)
- [RAG: documentos, embeddings y recuperación](docs/rag.md)
- [Límites y respuestas 429/503](docs/rate-limits.md)
- [Consola web](docs/web-console.md)
- [Validación y límites conocidos](docs/validation.md)

El entorno Compose es para desarrollo local; el despliegue productivo está pendiente.
