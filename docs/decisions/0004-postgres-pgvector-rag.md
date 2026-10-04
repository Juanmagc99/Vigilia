# ADR 0004: conocimiento operativo con pgvector

## Estado

Aceptada para la primera versión del RAG.

## Contexto

Las investigaciones necesitan incorporar runbooks y otra documentación operacional
sin acoplar el dominio al proveedor que genera texto. El sistema ya persiste el ciclo
de vida de investigaciones en PostgreSQL y ya entrega al analizador un
`InvestigationContext` extensible.

## Decisión

- Guardar documentos y fragmentos en PostgreSQL y sus embeddings con pgvector.
- Usar búsqueda exacta por distancia coseno al inicio; medir antes de añadir un índice
  aproximado.
- Encapsular embeddings detrás de `EmbeddingProvider`, implementado inicialmente
  mediante LiteLLM y configurado independientemente del modelo de análisis.
- Incorporar la recuperación al worker antes de `IncidentAnalyzer`.
- Aislar consultas por entorno y por servicio, permitiendo explícitamente documentos
  compartidos con el servicio `*`.
- Recibir el texto por un endpoint autenticado. Las integraciones con Git, Wiki o
  almacenamiento de archivos quedan para adaptadores futuros.
- Mantener RAG apagado por defecto para que el comportamiento local actual no genere
  llamadas ni coste de embeddings sin configuración explícita.

## Consecuencias

- Compose debe usar una imagen PostgreSQL con pgvector y Alembic debe crear la
  extensión y las tablas.
- Cambiar el modelo de embeddings exige reindexar los documentos; la búsqueda omite
  embeddings creados con otro identificador de modelo.
- La búsqueda exacta ofrece recuerdo completo y operación simple en corpus pequeños,
  pero requiere medir rendimiento a medida que crezca el índice.
- Las investigaciones completadas guardan los fragmentos recuperados y las citas
  validadas para permitir auditoría posterior.
- El proveedor recibe el texto enviado a indexación y las consultas de incidentes;
  el despliegue debe aplicar las políticas de privacidad correspondientes.

## Alternativas descartadas por ahora

- Un vector store externo añadiría otro servicio y credenciales antes de demostrar la
  necesidad de escalar fuera de PostgreSQL.
- HNSW/IVFFlat pueden reducir latencia a costa de recuerdo/recursos; se incorporarán
  solo si las mediciones del corpus lo justifican.
- Conectores directos a distintas fuentes complicarían la primera iteración; el
  contrato de ingesta acepta texto y permite añadirlos después.
