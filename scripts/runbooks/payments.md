# Runbook ficticio: pagos indisponibles y pool de conexiones

Estado: material sintético derivado de fixtures antiguos de desarrollo; no usar
como procedimiento de producción.

## Alertas relacionadas

- Incidente de servicio `payments`, título de ejemplo `Payments unavailable`,
  severidad `critical`.
- Posible causa de demostración: agotamiento del pool de conexiones a la base de
  datos.
- Impacto de demostración: respuestas HTTP 500 durante aproximadamente cinco
  minutos. Estos valores son ejemplos, no mediciones reales.

## Diagnóstico inicial

1. Confirma el alcance: tasa de errores, latencia, rutas afectadas y hora de inicio.
2. Comprueba disponibilidad y saturación de PostgreSQL, conexiones activas y
   rechazadas, esperas del pool y consultas lentas.
3. Revisa si hubo un aumento de tráfico, transacción bloqueada o despliegue justo
   antes del incidente.
4. Distingue agotamiento del pool de una caída de PostgreSQL; no aumentes el tamaño
   del pool sin verificar el límite total de conexiones de la base de datos.

## Mitigación y recuperación

- Si PostgreSQL está disponible pero saturado, identifica las consultas o workers
  responsables y sigue los límites aprobados para reducir carga.
- Si la saturación coincide con un cambio reciente, evalúa revertir ese cambio con
  el responsable del servicio.
- No mates sesiones ni reinicies la base de datos como primer paso: pueden ampliar
  el impacto o perder trabajo en curso.
- Confirma la recuperación observando conexiones, errores HTTP y latencia durante
  una ventana estable. Registra duración e impacto confirmados, sin asumir los cinco
  minutos del ejemplo.

## Evidencias útiles

Métricas del pool y PostgreSQL, consultas lentas, errores HTTP, tráfico, cambios
recientes y cronología de mitigación.
