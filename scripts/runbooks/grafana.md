# Runbook ficticio: alertas de prueba y entrega del webhook de Grafana

Estado: material sintético para validar Vigilia localmente; no usar como runbook de
producción.

## Alertas relacionadas

- `TestAlert` del fixture de notificación de Grafana, servicio/instancia `Grafana`,
  resumen `Notification test`.
- `SyntheticAlert`, `CpuHigh` y `MemoryHigh` enviados por
  `scripts/send_grafana_alert.py`.

## Interpretación

`TestAlert` y `Notification test` validan la ruta de notificación; no indican por sí
solos una caída de Grafana ni de un servicio de negocio. Las alertas sintéticas del
script también son datos de demostración y no se basan en métricas reales.

## Comprobación de entrega local

1. Verifica que Grafana y Vigilia están disponibles en los puertos locales 3000 y
   8000.
2. Comprueba el destino del webhook `POST /webhooks/grafana` y que el secreto HMAC
   configurado coincida en ambos lados. No copies el secreto a logs o tickets.
3. Al usar `scripts/send_grafana_alert.py`, confirma una respuesta HTTP 202 y que
   las etiquetas incluyan `service`, `alertname` y `severity`.
4. Envía primero una alerta `firing` y luego `resolved` con el mismo servicio,
   nombre y fingerprint para verificar el ciclo completo.
5. Si hay error de autenticación, comprueba firma y timestamp; no desactives la
   verificación HMAC como solución.

## Evidencias útiles

Hora de envío, código HTTP, nombre de alerta, estado, etiquetas no sensibles y logs
de aplicación sin cabeceras de autenticación ni secretos.
