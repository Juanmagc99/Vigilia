# Runbook ficticio: CPU y memoria altas en payments-api

Estado: material sintético para desarrollo local; no usar como procedimiento de
producción.

## Alertas relacionadas

- `CpuHigh` (`warning`): CPU elevada en una instancia de `payments-api`.
- `MemoryHigh` (`critical`): memoria elevada en una instancia de `payments-api`.
- `SyntheticAlert`: alerta genérica enviada por `scripts/send_grafana_alert.py`.

## Diagnóstico inicial

1. Confirma si la alerta sigue en estado `firing` y qué instancia aparece en sus
   etiquetas. Una alerta `resolved` no requiere acciones de recuperación.
2. Comprueba si `CpuHigh` y `MemoryHigh` aparecen juntas y si aumentaron los errores
   HTTP o la latencia. Correlación temporal no demuestra por sí sola una causa común.
3. Revisa métricas recientes de CPU, memoria, reinicios, latencia y tasa de errores.
   Compara con el periodo anterior y con el tráfico recibido.
4. Busca despliegues o cambios de configuración próximos al inicio. No reinicies ni
   escales instancias sin comprobar primero capacidad, impacto y procedimiento del
   entorno.

## Mitigación y recuperación

- Si el consumo coincide con un aumento de tráfico, valida capacidad disponible y
  aplica únicamente el escalado aprobado para ese entorno.
- Si empezó tras un despliegue, compara la versión y sigue el procedimiento de
  rollback del servicio; conserva logs y marcas de tiempo.
- Si hay presión de memoria o reinicios, identifica el proceso y el patrón de
  crecimiento antes de cambiar límites o reiniciar.
- Da por recuperado el servicio cuando las métricas vuelvan a niveles normales y los
  errores y la latencia se mantengan estables. Confirma después que Grafana envía la
  transición `resolved`.

## Datos que aportar a la investigación

Ventana temporal, alertas activas, instancia afectada, métricas antes/después,
versión desplegada, cambios recientes y acciones realizadas.
