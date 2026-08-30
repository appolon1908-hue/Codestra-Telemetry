# Codestra OpenTelemetry Authority

Principal repository: `appolon1908-hue/Codestra-Telemetry`
Canonical service host: `otel.codestra.media`
Canonical DNS target: `37.27.128.39`

Use no alternate authoritative hostname.

## Ownership
Own OpenTelemetry Collector configuration, receivers, processors, exporters, pipelines, sampling/redaction policy, telemetry transport validation and upgrade runbooks. Do not own application business logic, Grafana dashboards, Loki/Tempo/Prometheus storage or Caddy.

## Exposure
Private/internal only. DNS may exist; Collector OTLP/admin ports must not be public. Only approved application/private-network sources may submit telemetry.

## Integration
Upstream: instrumented applications, gateways and approved agents/Alloy. Downstream: Prometheus-compatible metrics targets, Loki-approved log paths and Tempo traces as configured.

## Branch policy
Persistent: `main`, `development`, `test`, `staging`, `production`. Temporary: `feature/*`, `fix/*`, `upgrade/*`, `security/*`, `docs/*`, `hotfix/*`, optional `release/*`, `rollback/*`. Promotion: work -> development -> test -> staging -> production -> main.
