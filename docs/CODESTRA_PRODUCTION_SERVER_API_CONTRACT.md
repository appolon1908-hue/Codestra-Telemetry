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
| OTLP/HTTP | `POST /v1/traces` | trace ingestion | private mTLS |
| OTLP/HTTP | `POST /v1/metrics` | metric ingestion | private mTLS |
| OTLP/HTTP | `POST /v1/logs` | log ingestion | private mTLS |
| HTTP | health endpoint | readiness/liveness | private/read-only |
| HTTP | metrics endpoint | collector self-metrics | private Prometheus scrape |

Unexpected `404`, unhandled `5xx`, unauthenticated acceptance, or caller-selected business identity blocks production.

## Identity, privacy, and routing

- `codestra_business` is overwritten from deployment-controlled workload identity.
- Wrong-business, wrong-audience, expired, and revoked credentials are denied.
- Sensitive attributes, secrets, cookies, raw bodies, database statements, customer identifiers, and financial/trading payloads are deleted, hashed where approved, or rejected before export.
- Queues, retries, memory limits, batching, backpressure, and dropped/rejected telemetry metrics are mandatory.
- Prometheus remains metric/SLO/alert authority; Loki remains log authority; Tempo remains trace authority.
- Native ingestion ports are never publicly exposed.

## Production gates

```text
PROTECTED_PRODUCTION_SHA=PASS
CONFIG_VALIDATION=PASS
OTLP_CONTRACT_TESTS=PASS
REDACTION_FIXTURES=PASS
QUEUE_BACKPRESSURE_TESTS=PASS
TENANT_OVERRIDE_TESTS=PASS
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
POST_/v1/traces_ROUTE_EXISTS=PASS
POST_/v1/metrics_ROUTE_EXISTS=PASS
POST_/v1/logs_ROUTE_EXISTS=PASS
HEALTH_ENDPOINT=PASS
METRICS_ENDPOINT=PASS
MTLS=PASS
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

Use synthetic fixtures only. Prove delivery to Loki, Prometheus, and Tempo and readback through Grafana without creating a second storage or alert authority.

## Repository-first remediation

Any deployment defect must be fixed in this repository with a regression test, committed, pushed, reviewed, merged, rebuilt, signed, and recorded in the exact-digest BOM before retrying the server wave.

## Safety

This document does not deploy a collector or activate telemetry. SSH changes, business writes, external messaging, provider effects, lending, payments, and financial/trading mutation remain disabled.