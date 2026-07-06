# Vigilia: flujo actual y plan de incidentes

## Vision del proyecto

Vigilia es un backend construido con FastAPI que recibe alertas desde Grafana Alerting, las normaliza, las persiste en PostgreSQL y publica eventos en Redpanda/Kafka para que otros procesos puedan reaccionar a ellas.

La idea no es sustituir a Grafana. Grafana sigue siendo quien detecta condiciones de alerta y dispara webhooks. Vigilia anade una capa propia encima para responder preguntas como:

- que alerta llego
- como se normalizo
- como se persistio
- que evento se genero
- como se agrupan alertas relacionadas en incidentes
- como se generaran reportes mas adelante

El objetivo funcional es que Vigilia construya una historia operativa alrededor de las alertas: primero eventos atomicos, luego incidentes, luego reportes.

## Flujo actual de alertas

El flujo ya construido es:

```text
Grafana Alerting
  -> webhook HTTP
  -> FastAPI
  -> GrafanaWebhookPayload
  -> NormalizedAlert
  -> Alert en PostgreSQL
  -> AlertReceivedMessage
  -> Redpanda/Kafka topic alerts.received
  -> consumer de eventos
```

En terminos de carpetas:

```text
app/schemas/grafana.py
  Modelos de entrada segun el payload de Grafana.

app/schemas/alerts.py
  Modelo interno NormalizedAlert.

app/services/grafana_normalizer.py
  Convierte payloads de Grafana en alertas normalizadas.

app/db/models/alert.py
  Modelo persistente Alert.

app/repositories/alert_repository.py
  Guarda alertas normalizadas en PostgreSQL.

app/services/alert_ingestion_service.py
  Orquesta normalizar, guardar y publicar evento.

app/events/message.py
  Define AlertReceivedMessage.

app/events/publisher.py
  Publica eventos en Redpanda/Kafka.

app/events/consumer.py
  Consume eventos desde alerts.received.
```

## Kafka, Redpanda, publishers y consumers

Redpanda se esta usando como broker compatible con Kafka. Para Vigilia, se puede pensar como el servidor de eventos.

La configuracion actual apunta a:

```text
bootstrap servers: localhost:9092
topic principal: alerts.received
```

El modelo mental es:

```text
Publisher / Producer
  escribe mensajes en un topic

Topic
  canal/log donde se guardan eventos

Consumer
  lee mensajes de un topic

Worker
  proceso en background que ejecuta un consumer
```

En Vigilia:

```text
FastAPI publica eventos AlertReceived
Redpanda guarda esos eventos en alerts.received
app.events.consumer los lee
```

El consumer actual es minimo: lee el evento, valida el JSON como `AlertReceivedMessage` y lo loguea. El siguiente paso es que ese consumer llame al servicio de correlacion de incidentes.

## Conceptos clave

### Alert

Una `Alert` es un evento concreto recibido y guardado en base de datos.

Ejemplo:

```text
Alert #1
status=firing
fingerprint=a1b2
service=server-01.local
received_at=12:00
```

Si mas tarde llega el resolved, se guarda como otra fila:

```text
Alert #2
status=resolved
fingerprint=a1b2
service=server-01.local
received_at=12:10
```

Las dos filas son eventos distintos, aunque pertenecen a la misma instancia de alerta.

### Fingerprint

En Grafana, el fingerprint es un hash unico generado a partir del conjunto de labels y atributos de una instancia concreta de alerta.

Para Vigilia significa:

```text
fingerprint = identidad estable de una instancia de alerta
```

Sirve para unir el ciclo de vida de una alerta:

```text
HostDown server-01.local firing   fingerprint=a1b2
HostDown server-01.local resolved fingerprint=a1b2
```

El fingerprint es muy util para emparejar `firing` y `resolved` de la misma instancia de alerta, pero no debe confundirse con un incidente.

```text
fingerprint identifica una alerta concreta
incident agrupa varias alertas relacionadas
```

### Incident

Un `Incident` representa un problema operativo agrupado.

Ejemplo:

```text
Incident #1
service=server-01.local
status=open
```

Puede contener varias alertas:

```text
HostDown fingerprint=a1b2
HighCPU  fingerprint=c3d4
DiskFull fingerprint=e5f6
```

Aunque cada alerta tenga un fingerprint distinto, pueden formar parte del mismo incidente si afectan al mismo servicio o instancia y ocurren cerca en el tiempo.

### IncidentAlert

`IncidentAlert` es la tabla puente que une incidentes con alertas.

Modelo conceptual:

```text
incidents
  id = inc-1

incident_alerts
  incident_id = inc-1
  alert_id = alert-1
  incident_id = inc-1
  alert_id = alert-2

alerts
  alert-1 fingerprint=a1b2 status=firing
  alert-2 fingerprint=c3d4 status=firing
```

Esta tabla permite reconstruir el timeline del incidente a partir de eventos concretos de alerta.

## Regla funcional de correlacion v1

La primera version de correlacion debe ser determinista y facil de entender.

### Cuando llega una alerta firing

Regla:

```text
Buscar incidente abierto reciente con el mismo service.

Si existe:
  asociar la alerta a ese incidente.

Si no existe:
  crear un incidente nuevo.
```

El `service` sale de la normalizacion:

```text
labels["service"] o labels["instance"] o "unknown"
```

Para evitar que un incidente abierto durante demasiado tiempo absorba alertas no relacionadas, se usara una ventana temporal configurable:

```text
VIGILIA_INCIDENT_CORRELATION_WINDOW_MINUTES=30
```

### Cuando llega una alerta resolved

Regla:

```text
Buscar incidente abierto que ya contenga una alerta con el mismo fingerprint.

Si existe:
  asociar el evento resolved a ese incidente.
  recalcular el ultimo estado por fingerprint.

Si no existe:
  loguear que llego un resolved sin incidente abierto asociado.
```

Para `resolved` se busca por fingerprint porque el resolved pertenece a una instancia concreta de alerta que ya habia estado firing.

### Como decidir si un incidente se resuelve

Un incidente no se resuelve solo porque llegue un `resolved`.

Se resuelve cuando todos los fingerprints asociados al incidente tienen como ultimo estado conocido `resolved`.

Ejemplo:

```text
Incident #1
  cpu-api    firing
  memory-api firing
  cpu-api    resolved
```

Ultimo estado por fingerprint:

```text
cpu-api    = resolved
memory-api = firing
```

El incidente sigue abierto.

Luego llega:

```text
memory-api resolved
```

Ultimo estado:

```text
cpu-api    = resolved
memory-api = resolved
```

Entonces:

```text
Incident #1 -> resolved
```

## Archivos nuevos para incidentes

La vertical de incidentes se organiza asi:

```text
app/db/models/incident.py
  Modelo persistente Incident.

app/db/models/incident_alert.py
  Tabla puente entre Incident y Alert.

app/repositories/incident_repository.py
  Funciones de lectura/escritura para incidentes.

app/services/incident_correlation_service.py
  Reglas de negocio para crear, actualizar o resolver incidentes.
```

Tambien se tocaran:

```text
app/core/config.py
  Configuracion de ventana temporal.

.env
  Valor de VIGILIA_INCIDENT_CORRELATION_WINDOW_MINUTES.

app/events/consumer.py
  Para que el worker llame al correlator.

migrations/versions/...
  Migracion de incidents e incident_alerts.
```

## Responsabilidades por capa

### Models

Definen que existe en la base de datos.

```text
Alert
Incident
IncidentAlert
```

### Repositories

Saben leer y escribir en la base de datos, pero no deberian contener demasiada decision de negocio.

Ejemplos:

```text
find_recent_open_incident_for_service
find_open_incident_by_fingerprint
create_incident_from_alert
attach_alert_to_incident
get_latest_alert_statuses_for_incident
resolve_incident
```

### Services

Aplican reglas de negocio.

El servicio central sera:

```text
app/services/incident_correlation_service.py
```

Su funcion principal:

```text
correlate_alert(session, alert)
```

Decide:

```text
si alert.status == firing:
  buscar/crear incidente y asociar alerta

si alert.status == resolved:
  buscar incidente por fingerprint
  asociar resolved
  cerrar incidente si ya no quedan fingerprints activos
```

### Events

Conectan Kafka/Redpanda con la logica de negocio.

El consumer debe pasar de:

```text
AlertReceivedMessage
```

a:

```text
Alert cargada desde PostgreSQL
```

y luego llamar a:

```text
correlate_alert(session, alert)
```

## Flujo objetivo de incidentes

El flujo completo objetivo queda asi:

```text
Grafana webhook
  -> FastAPI
  -> normalizar alertas
  -> guardar Alert en PostgreSQL
  -> publicar AlertReceivedMessage en alerts.received

Consumer / worker
  -> leer AlertReceivedMessage
  -> cargar Alert por alert_id
  -> llamar incident_correlation_service.correlate_alert
  -> crear, actualizar o resolver Incident
```

## Ejemplo completo

Llegan estas alertas:

```text
12:00 HostDown  server-01 fingerprint=a1b2 status=firing
12:03 HighCPU   server-01 fingerprint=c3d4 status=firing
12:10 HostDown  server-01 fingerprint=a1b2 status=resolved
12:15 HighCPU   server-01 fingerprint=c3d4 status=resolved
```

Resultado:

```text
12:00
  No hay incidente abierto.
  Crear Incident #1.
  Asociar HostDown firing.

12:03
  Hay incidente abierto reciente para server-01.
  Asociar HighCPU firing.

12:10
  Buscar incidente abierto que contiene fingerprint=a1b2.
  Asociar HostDown resolved.
  Ultimos estados:
    a1b2 = resolved
    c3d4 = firing
  Incident #1 sigue open.

12:15
  Buscar incidente abierto que contiene fingerprint=c3d4.
  Asociar HighCPU resolved.
  Ultimos estados:
    a1b2 = resolved
    c3d4 = resolved
  Incident #1 pasa a resolved.
```

## Orden recomendado de implementacion

1. Terminar modelos `Incident` e `IncidentAlert`.
2. Crear migracion Alembic para `incidents` e `incident_alerts`.
3. Completar `incident_repository.py`.
4. Crear `incident_correlation_service.py`.
5. Conectar `app/events/consumer.py` con DB y correlator.
6. Probar manualmente con Grafana, PostgreSQL y Redpanda.
7. Dejar testing automatizado para el final de esta fase, como decision consciente.

## Decisiones tomadas

- No llamar a IA por alerta individual.
- Usar IA mas adelante sobre incidentes y reportes, no sobre alertas sueltas.
- Usar fingerprint para emparejar eventos de la misma instancia de alerta.
- Usar service/instance y ventana temporal para agrupar alertas en incidentes.
- Resolver incidentes solo cuando todos sus fingerprints asociados tengan ultimo estado `resolved`.
- Mantener la primera version simple, determinista y explicable.

