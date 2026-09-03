# Codestra OpenTelemetry Production Server and Native API Contract

## Authority

- Repository: `appolon1908-hue/Codestra-Telemetry`
- Role: OTLP ingress, normalization, redaction, sampling, buffering, and backend-routing authority
- Canonical hostname: `otel.codestra.media`
- Central production host: `37.27.128.39`
- Core host `65.109.65.169`: approved application telemetry source only
- Status: `SOURCE_CONTRACT_PREPARED_NOT_DEPLOYED`

This repository owns the collector configuration, telemetry contract, native OTLP API boundary, queues, redaction, source locks, release evidence, recovery, and rollback. It has no business mutation, communications, secret-authority, lender, payment, or trading authority.

## Native API surface

| Protocol | Endpoint | Purpose | Boundary |
|---|---|---|---|
| OTLP/gRPC | `:4317` | traces, metrics, and logs | private mTLS |
| OTLP/HTTP | `:4318 POST /v1/traces` | trace ingestion | private mTLS |
| OTLP/HTTP | `:4318 POST /v1/metrics` | metric ingestion | private mTLS |
| OTLP/HTTP | `:4318 POST /v1/logs` | log ingestion | private mTLS |
| HTTP | `:13133/` | Collector health-check extension | private/read-only |
| HTTP | `:8888/metrics` | Collector process, receiver, processor, queue, refusal, and exporter self-metrics | private Prometheus scrape |
| HTTP | `:8889/metrics` | sanitized OTLP application metrics converted to OpenMetrics | private Prometheus scrape |

OTLP endpoints bind only to the `otel-collector-platform-ingress` alias on the
business telemetry network. Health and metrics endpoints bind only to the
`otel-collector-platform-metrics` alias on the observability network. The
generic `otel-collector` alias and wildcard listeners are prohibited because
they make ports reachable across both attached networks.

Unexpected `404`, unhandled `5xx`, unauthenticated acceptance, an unavailable required native port, or caller-selected business identity blocks production.

## Identity, privacy, and routing

- The authoritative resource key is `codestra.business`; it is overwritten from deployment-controlled workload identity.
- Before the authoritative value is installed, the Collector deletes both caller spellings: `codestra.business` and `codestra_business`. The underscore form is also deleted from incoming span, event, log, and metric attributes before any safe metric label is generated.
- The generated Prometheus label `codestra_business` is created only from the authoritative `codestra.business` resource value after sanitization.
- Wrong-business, wrong-audience, expired, and revoked credentials are denied.
- Sensitive attributes, secrets, cookies, raw bodies, database statements, customer identifiers, and financial/trading payloads are deleted, hashed where approved, or rejected before export.
- Queues, retries, memory limits, batching, backpressure, and dropped/rejected telemetry metrics are mandatory.
- Prometheus owns both private scrape targets `:8888/metrics` and `:8889/metrics`, plus target labels, recording rules, alert evaluation, and retention.
- Prometheus remains metric/SLO/alert authority; Loki remains log authority; Tempo remains trace authority.
- Native ingestion and scrape ports are never publicly exposed.
- The repository-controlled business identity is exactly `platform`; an
  unknown or caller-supplied business value fails before Collector startup.

## Production gates

```text
PROTECTED_PRODUCTION_SHA=PASS
CONFIG_VALIDATION=PASS
OTLP_CONTRACT_TESTS=PASS
REDACTION_FIXTURES=PASS
QUEUE_BACKPRESSURE_TESTS=PASS
TENANT_OVERRIDE_TESTS=PASS
CALLER_CODESTRA_BUSINESS_FORMS_SANITIZED=PASS
OTLP_HTTP_4318=PASS
SELF_METRICS_8888=PASS
APPLICATION_METRICS_8889=PASS
HEALTH_13133=PASS
IMMUTABLE_IMAGE_DIGEST=PASS
IMAGE_SIGNATURE=PASS
SBOM=PASS
PROVENANCE=PASS
SECRET_SCAN=PASS
VULNERABILITY_GATE=PASS
ROLLBACK_MANIFEST=PASS
```

## Runtime certification

```text
OTLP_GRPC_4317=PASS
OTLP_HTTP_4318=PASS
POST_4318_/v1/traces_ROUTE_EXISTS=PASS
POST_4318_/v1/metrics_ROUTE_EXISTS=PASS
POST_4318_/v1/logs_ROUTE_EXISTS=PASS
HEALTH_13133=PASS
SELF_METRICS_8888=PASS
APPLICATION_METRICS_8889=PASS
MTLS=PASS
AUTHORITATIVE_CODESTRA_DOT_BUSINESS_OVERWRITTEN=PASS
CALLER_CODESTRA_BUSINESS_UNDERSCORE_REMOVED=PASS
CALLER_BUSINESS_OVERRIDE_DENIED=PASS
WRONG_ROLE_DENIED=PASS
EXPIRED_CREDENTIAL_DENIED=PASS
REVOKED_CREDENTIAL_DENIED=PASS
QUEUE_AND_BACKPRESSURE=PASS
SENSITIVE_OUTPUT=0
UNEXPECTED_404=0
UNEXPECTED_5XX=0
SOURCE_RUNTIME_DRIFT=0
```

Certification must fail when `:8888/metrics` succeeds but `:8889/metrics` is unavailable, empty for a valid synthetic metric, or contains a caller-supplied business value. Use synthetic fixtures only. Prove delivery to Loki, Prometheus, and Tempo and readback through Grafana without creating a second storage or alert authority.

## Repository-first remediation

Any deployment defect must be fixed in this repository with a regression test, committed, pushed, reviewed, merged, rebuilt, signed, and recorded in the exact-digest BOM before retrying the server wave.

## Safety

This document does not deploy a collector or activate telemetry. SSH changes, business writes, external messaging, provider effects, lending, payments, and financial/trading mutation remain disabled.
