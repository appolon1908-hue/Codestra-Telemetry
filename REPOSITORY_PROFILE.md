# Repository Profile — `Codestra-Telemetry`

## Identity

- **Repository:** `appolon1908-hue/Codestra-Telemetry`
- **Category:** Observability pipeline — OpenTelemetry Collector
- **Visibility:** `public`
- **Default branch:** `main`
- **Canonical hostname:** `otel.codestra.media`
- **Exposure:** Internal/private only; OTLP receivers must not be Internet-public
- **Authority:** Primary OpenTelemetry receiver, processor, redaction, sampling, batching, retry, and export-pipeline authority

## Purpose

Receives approved metrics, logs, and traces; enriches and redacts telemetry; applies batching, memory limits, sampling, queues, retries, and forwards data to accepted observability backends.

## Owns

- OTLP and approved receiver configurations
- Resource detection, enrichment, filtering, redaction, sampling, batching, memory limiting, retry, queue, and exporter pipelines
- Collector health, diagnostics, validation, upgrade, and rollback source

## Does not own

- Application instrumentation source
- Long-term metrics, log, or trace storage
- Public unauthenticated telemetry ingestion

## Key integrations

- Applications and agents using OTLP
- Prometheus-compatible metrics path
- Loki and Tempo
- Alloy where collection ownership is explicitly divided

## Current priorities

1. Finalize pipeline ownership to avoid duplicate telemetry
2. Enforce PII/secret redaction and bounded resource attributes
3. Prove queueing, retries, backpressure, outage recovery, and synthetic telemetry
4. Add configuration, performance, upgrade, and rollback evidence

## Governance and safety

- Promotion model: `feature/docs/fix/security/upgrade -> development -> test -> staging -> production -> main`.
- Native OTLP ports `4317/4318` and diagnostics must remain private or protected by approved network controls.
- Never commit exporter credentials, private keys, customer payloads, tokens, or secret-bearing telemetry fixtures.
- New receivers/exporters require ownership, security, cardinality, and retention review.
- Merge does not start the Collector, open receivers, forward telemetry, alter storage, or deploy software.

## Account-wide catalog

See `appolon1908-hue/documentaions/REPOSITORY_CATALOG.md`.
