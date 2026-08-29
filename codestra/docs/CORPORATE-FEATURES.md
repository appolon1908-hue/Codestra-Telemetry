# Codestra OpenTelemetry Corporate Features

## Mission

OpenTelemetry is the vendor-neutral instrumentation and telemetry routing standard for every Codestra-managed application. Applications emit one consistent telemetry model; the collector normalizes, redacts, batches and routes signals to Prometheus, Loki and Tempo.

## Standard application envelope

Required resource attributes:

- `service.name`
- `service.version`
- `deployment.environment`
- `codestra.business`
- `codestra.region`
- `codestra.deployment`

Application events should preserve safe `codestra.correlation_id`, `codestra.command_id`, operation/result/error information and W3C trace context.

## Corporate features

- OTLP gRPC and HTTP ingestion;
- resource detection and normalization;
- centralized attribute redaction;
- batching and memory limits;
- environment/business routing;
- error/high-latency sampling policies;
- collector health/self-metrics;
- backpressure and dropped-telemetry visibility;
- standardized exporters to metrics/log/trace backends;
- consistent instrumentation libraries and semantic conventions across Python, TypeScript and other Codestra services.

## Business onboarding

A new Codestra business should only need to declare its business ID, service name, version and environment. It then automatically fits the same Grafana, Prometheus, Loki and Tempo model instead of creating another monitoring architecture.

## Privacy/security

The collector must remove secret-bearing headers and sensitive attributes before export. Raw request/response bodies are not part of the telemetry contract. TLS is required when telemetry crosses an untrusted network boundary, and runtime credentials come from OpenBao or an approved secret-injection mechanism.

## Beyvra trading rule

Trading telemetry may contain safe operation names, latency, result/error codes, reconciliation state and provider identity where approved. It must never contain signing keys, provider credentials, raw authorization material, full sensitive order payloads or customer financial secrets.

## Release rule

`otel.codestra.media` remains internal/private. Collector configuration changes are reviewed in Git and do not activate deployment merely by merging.
