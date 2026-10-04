# RAG y conocimiento operativo en Vigilia

Este documento explica la implementación del flujo de recuperación aumentada (RAG)
de Vigilia: cómo cargar conocimiento, cómo se indexa, cómo llega a una investigación,
cómo se validan sus referencias y qué límites operativos tiene.

## Objetivo

RAG permite que una investigación use documentación propia de Vigilia, como runbooks,
procedimientos y postmortems. No entrena ni modifica el LLM. Vigilia recupera texto
relevante en tiempo de ejecución y lo entrega al analizador junto con las alertas.
El contenido se mantiene como evidencia independiente; el modelo no decide qué
documentos tiene permiso para consultar.

## Componentes y responsabilidades

- `application/knowledge.py` normaliza y fragmenta texto, valida límites, coordina la
  creación de embeddings, indexa documentos y construye la consulta del incidente.
- `application/ports.py` define `EmbeddingProvider`, `KnowledgeRetriever` y las
  operaciones de índice requeridas por los casos de uso.
- `adapters/llm/embeddings.py` implementa embeddings usando LiteLLM. El modelo de
  embeddings se configura aparte del modelo de análisis.
- `adapters/postgres/models.py` define documentos y fragmentos. La columna vectorial
  se guarda con pgvector en la misma base que los demás datos.
- `adapters/postgres/repositories.py` reemplaza de forma transaccional los fragmentos
  de un documento y busca vecinos por distancia coseno.
- `ExecuteInvestigation` llama al recuperador después de reclamar el trabajo y crear
  el snapshot del incidente, justo antes de `IncidentAnalyzer`.
- El adaptador LiteLLM integra las fuentes como `knowledge:<uuid>` y rechaza cualquier
  cita que no pertenezca al contexto de esa investigación.

## Ingesta de documentos

La ingesta recibe texto Markdown o texto plano. No descarga direcciones URL ni lee
repositorios por su cuenta: el cliente que llama a la API envía el contenido y sus
metadatos. El documento queda identificado por `service + environment + source`.
Enviar otra versión con esa misma identidad reemplaza atómicamente sus fragmentos;
la versión previa deja de participar en búsquedas. Las investigaciones completadas
conservan una copia de los fragmentos recuperados y la versión que consultaron.

Antes de generar embeddings, Vigilia:

1. recorta espacios exteriores y redacta patrones comunes de credenciales (Bearer,
   password, secret, API key y access token);
2. rechaza contenido vacío o mayor que `VIGILIA_RAG_MAX_DOCUMENT_CHARACTERS`;
3. divide el texto en fragmentos de hasta `VIGILIA_RAG_CHUNK_SIZE` caracteres, con
   solapamiento configurable para no cortar el contexto entre fragmentos;
4. pide embeddings en lotes configurables mediante el adaptador LiteLLM;
5. guarda metadatos, hash SHA-256 del texto ya redactado, fragmentos y vectores en
   una transacción PostgreSQL.

La redacción de credenciales cubre patrones sencillos; no es un detector universal de
secretos. Conviene no enviar credenciales a la API de conocimiento. El contenido se
envía al proveedor de embeddings configurado, por lo que hay que aplicar al corpus
las mismas reglas de privacidad que al contexto enviado al LLM.

El repositorio incluye runbooks ficticios en `scripts/runbooks/` para poblar el
entorno local y practicar la recuperación con alertas sintéticas: CPU/memoria de
`payments-api`, indisponibilidad/pool de conexiones de `payments`, y comprobación de
webhooks de Grafana. No son procedimientos validados para producción. El script
`scripts/seed_knowledge.py` los envía a `POST /knowledge/documents`; repetir la carga
reemplaza la versión anterior por la identidad `service + environment + source`.

## Recuperación durante una investigación

El recuperador forma una consulta con servicio, título, severidad y nombres,
resúmenes y descripciones de las alertas del snapshot. Calcula el embedding con el
mismo modelo usado al indexar y solicita hasta `VIGILIA_RAG_TOP_K` fragmentos. La
búsqueda exige que coincidan el modelo y dimensión de embeddings y el entorno; filtra además al
servicio afectado o a documentos globales con `service="*"`. Así no mezcla
conocimiento de otro servicio o entorno.

Los fragmentos se ordenan por distancia coseno creciente. El recuperador limita el
texto acumulado a `VIGILIA_RAG_MAX_CONTEXT_CHARACTERS` y lo agrega a
`InvestigationContext.knowledge`. Si no existe documentación coincidente, la
investigación continúa con las alertas sin conocimiento adicional. Si el proveedor
de embeddings falla temporalmente, se aplica el mecanismo durable de reintentos de
investigaciones.

La versión inicial usa búsqueda exacta de pgvector, que compara los vectores
coincidentes y prioriza el recuerdo completo. No crea un índice HNSW aproximado:
para corpus pequeños y medianos evita intercambiar calidad por velocidad. Si el
volumen real lo exige, se medirán latencia y tamaño del corpus antes de elegir HNSW,
IVFFlat o una estrategia de particionado. Un índice aproximado puede afectar el
recuerdo y requiere volver a evaluar los filtros por servicio.

## Evidencia y protección del análisis

Cada elemento de conocimiento tiene un UUID de fragmento y se presenta como
`knowledge:<uuid>`. El prompt indica que los campos del contexto son datos no
confiables: instrucciones encontradas dentro de un runbook o alerta no cambian las
reglas del sistema ni autorizan acciones.

El resultado persistido distingue:

- `evidence`: evidencias efectivamente citadas por las hipótesis del modelo;
- `retrieved_knowledge`: todos los fragmentos recuperados, con su texto, fuente,
  versión, servicio, similitud y `evidence_id`.

Por tanto se puede comprobar qué recuperó el sistema y cuáles de esos fragmentos
utilizó el modelo. El valor `similarity` es una puntuación de similitud coseno, no
una probabilidad de verdad ni un umbral de calidad calibrado.

## API protegida

Todos los endpoints de conocimiento requieren `Authorization: Bearer <token>` con
el mismo `VIGILIA_API_TOKEN` que protege incidentes.

### Crear o reemplazar un documento

`POST /knowledge/documents` recibe JSON:

```json
{
  "service": "payments",
  "source": "runbooks/payments.md",
  "title": "Diagnóstico de errores de conexión",
  "version": "2026-09",
  "content": "# Conexiones\n\nComprobar el pool y el estado de PostgreSQL..."
}
```

`service` puede ser `"*"` para conocimiento compartido dentro del mismo entorno.
La ruta devuelve `201` con el UUID del documento y el número de fragmentos creados.
El servicio crea los embeddings durante la petición, por lo que el timeout del
proveedor debe permitir indexar el documento completo.

### Retirar un documento

`DELETE /knowledge/documents/{document_id}` borra el documento y sus fragmentos. Los
resultados de investigaciones pasadas conservan sus copias de auditoría.

### Ejemplo con curl

```bash
curl -X POST http://localhost:8000/knowledge/documents \
  -H "Authorization: Bearer $VIGILIA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"payments","source":"runbooks/payments.md","title":"Runbook de pagos","version":"1","content":"Comprobar el pool de conexiones y la salud de PostgreSQL."}'
```

## Configuración

RAG queda desactivado por defecto. Para activarlo, configurar en `.env`:

```dotenv
VIGILIA_RAG_ENABLED=true
VIGILIA_RAG_EMBEDDING_MODEL=provider/embedding-model
VIGILIA_RAG_EMBEDDING_API_KEY=...
VIGILIA_RAG_EMBEDDING_API_BASE=...
```

Para que el modelo razone sobre los fragmentos recuperados, configura además el
analizador LiteLLM y su modelo de generación. El simulador sigue siendo determinista:
puede completar la investigación, pero no redacta conclusiones a partir del RAG.

LiteLLM acepta los identificadores de embedding de los proveedores que soporta y
también las variables de credenciales específicas reconocidas por LiteLLM. Se puede
definir `VIGILIA_RAG_EMBEDDING_API_KEY` y `VIGILIA_RAG_EMBEDDING_API_BASE` para
separar proveedor y credenciales. Si no se define una clave de embeddings, Vigilia
reutiliza `VIGILIA_LLM_API_KEY`, práctico cuando ambos modelos usan el mismo proveedor.
El modelo de embeddings debe ofrecer el mismo espacio y dimensiones al indexar
documentos y al buscar consultas.

| Variable | Valor predeterminado | Función |
| --- | --- | --- |
| `VIGILIA_RAG_ENABLED` | `false` | Activa ingesta y recuperación |
| `VIGILIA_RAG_EMBEDDING_MODEL` | sin valor | Modelo LiteLLM para embeddings; obligatorio al activar RAG |
| `VIGILIA_RAG_EMBEDDING_API_KEY` | usa `VIGILIA_LLM_API_KEY` si está configurada | Credencial específica de embeddings, útil si el proveedor es distinto |
| `VIGILIA_RAG_EMBEDDING_API_BASE` | sin valor | Endpoint opcional para ese modelo |
| `VIGILIA_RAG_EMBEDDING_TIMEOUT_SECONDS` | `30` | Timeout por llamada a embeddings |
| `VIGILIA_RAG_EMBEDDING_BATCH_SIZE` | `64` | Fragmentos por llamada durante la ingesta |
| `VIGILIA_RAG_CHUNK_SIZE` | `2400` | Tamaño máximo aproximado de fragmento en caracteres |
| `VIGILIA_RAG_CHUNK_OVERLAP` | `300` | Solapamiento entre fragmentos |
| `VIGILIA_RAG_MAX_DOCUMENT_CHARACTERS` | `250000` | Límite de contenido indexado por documento |
| `VIGILIA_RAG_TOP_K` | `5` | Número máximo de resultados candidatos |
| `VIGILIA_RAG_MAX_CONTEXT_CHARACTERS` | `16000` | Límite agregado de texto RAG por investigación |

Al cambiar el modelo de embeddings hay que volver a enviar cada documento para
regenerar sus vectores. Mientras un documento tenga otro `embedding_model` o dimensión,
la búsqueda actual lo omite; esto evita comparar vectores de espacios distintos.

## Arranque local y migraciones

Compose usa `pgvector/pgvector:pg17` para que PostgreSQL disponga de la extensión.
La migración Alembic crea `vector`, `knowledge_documents` y `knowledge_chunks`.
Al arrancar el stack de desarrollo, el servicio `migrate` aplica la migración. Para
reconstruir la imagen de la aplicación tras actualizar dependencias:

```bash
docker compose -f docker/docker-compose.dev.yaml up --build
```

Para usar una base PostgreSQL externa, su instalación debe permitir la extensión
pgvector antes de aplicar la migración. La búsqueda RAG se habilita solo en el
worker y la ingesta en la API cuando `VIGILIA_RAG_ENABLED=true`; apagarlo conserva
los documentos y vectores, pero evita llamadas de embeddings.

## Limitaciones deliberadas de esta versión

- El cliente entrega texto; no hay descarga automática desde Git, Wiki, Drive ni URLs.
- No hay extracción de PDF ni conversión HTML; esos adaptadores podrán añadirse sin
  cambiar el contrato de documento.
- No hay reranker, búsqueda híbrida por palabras clave ni filtro de similitud.
- La búsqueda exacta puede volverse lenta con corpus grandes; medir antes de añadir
  un índice aproximado.
- El consumo de embeddings no aparece todavía en la telemetría de coste de los
  intentos de análisis.
- Una investigación fallida antes de completarse no conserva los fragmentos en el
  resultado; sí los conserva cuando el análisis se completa.
- Los tests y la evaluación de calidad de recuperación siguen en el último bloque
  del roadmap, según el orden de trabajo acordado.
