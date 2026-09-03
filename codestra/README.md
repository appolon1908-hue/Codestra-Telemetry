# Codestra OpenTelemetry Collector authority

This directory is the Codestra runtime authority for receiving OTLP telemetry, applying tenant-safety controls, forwarding traces to Tempo and logs to Loki, and exposing OTLP application metrics for authoritative Prometheus scraping.

## Prometheus ownership

The Collector does not evaluate alerts, retain long-term application metrics, or replace native service instrumentation. It exposes two private scrape endpoints:

- `otel-collector-platform-metrics:8888/metrics`: the Collector's own process, receiver, processor, queue, refusal, and exporter metrics;
- `otel-collector-platform-metrics:8889/metrics`: sanitized OTLP application metrics converted to OpenMetrics.

`appolon1908-hue/Codestra-Prometheus` owns both scrape targets, target labels, sensitive-label stripping, recording rules, alert evaluation, and retention.

## Required sender resource attributes

Every service that sends OTLP metrics must provide these bounded resource attributes:

| Attribute | Example | Purpose |
|---|---|---|
| `codestra.application` | `beyvra` | product/application boundary |
| `service.name` | `orders-api` | deployable service identity |
| `service.version` | immutable commit or image digest | deployment evidence |
| `deployment.id` | immutable deployment identifier | rollout and rollback correlation |
| `deployment.environment.name` | `staging` | environment boundary |
| `host.name` | `codestra-core-01` | server boundary |
| `codestra.tenant_scope` | `aggregate` | tenant-safety declaration |

The metrics pipeline copies only the canonical application, service, environment, server, and aggregate tenant-scope values into metric labels. It does not convert all resource attributes into labels.

## Tenant and cardinality safety

The resource and datapoint processors delete known tenant, organization, customer, account, user, email, phone, credential, session, request, correlation, trace, span, lead, order, message, workflow, execution, webhook, idempotency, raw path, URL, query, client address, database statement, host ID, container ID, and service-instance ID attributes. The central Prometheus authority applies a second label-drop boundary.

Telemetry payloads must never contain passwords, tokens, full message bodies, payment data, document contents, call recordings, raw SQL, email bodies, phone numbers, or unbounded IDs. Logs must be structured and redacted before transmission; the Collector's attribute deletion is defense in depth, not permission to emit sensitive log bodies.

## Private network boundary

- Applications reach `otel-collector-platform-ingress` on OTLP gRPC `4317` or OTLP HTTP `4318` only on `codestra-telemetry-platform`.
- Prometheus and operators reach `otel-collector-platform-metrics` on `8888`, `8889`, and `13133` only on `codestra-observability`.
- The Collector binds each listener to its network-specific alias. OTLP does not listen on the shared observability interface, and scrape/health endpoints do not listen on the business-ingress interface.
- No port receives a host `ports:` mapping, public DNS route, Caddy route, Kong route, or Internet firewall allowance.
- `otel.codestra.media` must not be activated until a separate authenticated, rate-limited, tenant-safe ingress design is approved.

## Validation

```bash
cp codestra/.env.example codestra/.env
# Set OTEL_COLLECTOR_IMAGE to a reviewed digest.
docker compose --env-file codestra/.env -f codestra/compose.yaml config
otelcol-contrib validate --config codestra/collector.yaml
```

Before activation, validate positive and negative OTLP fixtures, verify deleted attributes never appear at `8889`, prove private-only reachability, confirm Tempo and Loki retry/queue behavior, scrape `8888` and `8889` with canonical labels, test exporter failure alerts, and perform rollback.

Promotion is `feature/* -> development -> test -> staging -> production -> main`. Merging does not deploy or expose OTLP publicly.
