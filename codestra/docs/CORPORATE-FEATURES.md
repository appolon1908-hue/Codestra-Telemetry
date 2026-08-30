# Codestra OpenTelemetry Corporate Features

## Mission

The Codestra OpenTelemetry Collector is the governed telemetry ingress, normalization, redaction, sampling and routing layer for Codestra and every managed business. It converts application telemetry into the bounded corporate contracts consumed by Prometheus, Tempo and Loki.

The Collector is not a business system, identity provider, incident router, communications platform, secrets authority, data warehouse or trading engine.

## Business isolation

Each Collector instance belongs to exactly one approved business:

- `platform`
- `codestra`
- `moneybee`
- `beyvra`
- `breero`
- `larim-a`
- `transportation`
- `booked4seasons`
- `social`
- `klyrow`
- `telnexa`
- `kyqra`
- `restaurant`
- `provisioning`

The deployment controller sets `CODESTRA_BUSINESS`; the Collector overwrites any caller-supplied `codestra.business` value. Each instance joins one business-specific ingress network plus the shared private observability network. Unknown business IDs and cross-business network access are release blockers.

OTLP/gRPC and OTLP/HTTP require a server certificate, private key and trusted client CA. Direct browser ingestion is prohibited. Browser telemetry must pass through an approved same-origin or backend path that applies rate limits, consent and data-minimization controls.

## Required workload identity

Every workload must provide:

- `codestra.application`
- `service.name`
- `service.version`
- `deployment.id`

The Collector adds or overwrites:

- `codestra.business`
- `deployment.environment.name`
- `cloud.region`
- `host.name`
- aggregate tenant scope
- Collector deployment identity

Telemetry without required workload identity is dropped instead of being grouped into an ambiguous corporate service.

## Canonical metric representation

Prometheus receives only bounded labels:

- `codestra_business`
- `application`
- `service`
- `service_version`
- `environment`
- `deployment`
- `region`
- `server`
- `tenant_scope`

Customer, account, user, request, trace, message, order, workflow, raw URL, SQL, exception, container, pod and process identifiers are removed before metric export. Product instrumentation must use normalized routes, bounded operations, bounded provider names, response classes, result enums and controlled error codes.

## Logs and traces

Logs and traces preserve intrinsic trace/span correlation while removing duplicate high-cardinality attributes. Logs must be structured and pre-redacted by the application or Alloy before they reach this gateway. Authorization data, cookies, credentials, raw bodies, database statements, customer identifiers, and broker/exchange signing material are removed or rejected.

Loki and Tempo receive a deployment-controlled `X-Scope-OrgID` equal to the approved Codestra business. Caller-supplied tenant headers are never trusted.

## Tail sampling

The Collector preserves:

- all error-status traces;
- traces at or above two seconds;
- traces explicitly marked with security, reconciliation, capability, financial or delivery priority.

Routine successful traces are sampled at ten percent. Sampling percentages are engineering defaults until calibrated with staging traffic, storage, latency and incident-reconstruction evidence. Sampling must never remove the only evidence for a critical business path.

## Delivery durability

Tempo and Loki exporters use bounded file-backed queues and retry with exponential backoff. Queue state is stored on a durable Collector volume. This protects short backend outages, but it is not a business transaction ledger and does not guarantee unlimited retention. Prometheus metrics remain pull-based.

## Corporate paths

The standard supports:

- edge and gateway requests;
- identity and authorization;
- Middleware orchestration;
- Odoo and n8n integration;
- PostgreSQL and Redis dependencies;
- outbox, inbox, workers and queues;
- email, SMS, voice, social, scraper and provider adapters;
- deployments, configuration and capability changes;
- authentication failures, authorization denials, idempotency conflicts and reconciliation failures;
- Beyvra market-data and trading-path health using safe aggregate metadata only.

## Beyvra boundary

The Collector may process safe aggregate provider health, market-data freshness, request latency, reconciliation result and capability state. It must remove credentials, signing material, raw order payloads, account IDs, balances, positions and executions. It never places, changes, cancels or approves a trade.

## Release rule

The native OTLP ports remain private. Promotion is `feature/* -> development -> test -> staging -> production -> main`. Merge or CI success does not create certificates, join networks, activate backends, ingest production telemetry, enable communications delivery or authorize a business mutation.
