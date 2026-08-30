# Codestra Fourteen-Authority Suite Compatibility Gate V2

## Purpose

This gate binds the fourteen authorities that make up the Codestra observability, analytics, telemetry, exporter, alert-routing, and secrets source train. It records exact source evidence and ownership boundaries without creating a parallel runtime.

No deployment is authorized by this gate.

## Fourteen authorities

1. Grafana — read-only operational presentation.
2. Prometheus — metrics, SLOs, recording rules, and alert evaluation.
3. Alertmanager — grouping, inhibition, and Middleware-only alert routing.
4. Loki — business-isolated log storage and query.
5. Tempo — business-isolated distributed trace storage and query.
6. OpenTelemetry — application telemetry ingress, normalization, redaction, sampling, and routing.
7. Superset — certified read-only analytics with database-native row-level security.
8. Node Exporter — host and operational-evidence metrics.
9. cAdvisor — container resource metrics through a read-only Docker boundary.
10. PostgreSQL Exporter — least-privilege aggregate PostgreSQL health metrics.
11. Redis Exporter — read-only aggregate Redis health and persistence metrics.
12. Blackbox Exporter — bounded side-effect-free synthetic monitoring.
13. Alloy — business-scoped host and service log collection and redaction.
14. OpenBao — secrets, PKI, workload identity, leases, and cryptographic policy.

No component may absorb another component's authority.

## Required flow ownership

- Alloy and OpenTelemetry may send sanitized logs to Loki.
- OpenTelemetry, Node Exporter, cAdvisor, PostgreSQL Exporter, Redis Exporter, and Blackbox Exporter may provide bounded metrics to Prometheus.
- OpenTelemetry may send sanitized traces to Tempo.
- Prometheus may send evaluated alerts to Alertmanager.
- Alertmanager may route only to the prepared Middleware contract; direct email, SMS, voice, chat-provider, Odoo, n8n, financial, or trading delivery is prohibited.
- Grafana reads fixed Prometheus, Loki, and Tempo datasources.
- Superset reads certified datasets through read-only credentials and database-native row-level security.
- OpenBao supplies policy-scoped runtime identity, certificates, and secrets without controlling workload behavior.

## Business isolation

The deployment authority owns `codestra_business`. Caller-supplied business identity is not trusted. Folder permissions alone are insufficient. Loki and Tempo tenancy, Grafana datasource and role mapping, Superset database-native row-level security, and OpenBao business/application/environment policy isolation require negative tests before access is enabled.

Grafana and Superset business access remain disabled until those negative tests are recorded.

## Data minimization and security

Credentials, request or response bodies, database statements, customer identifiers, emails, phones, high-cardinality runtime identities, and broker, exchange, or custody signing material may not be indexed or exposed through the suite.

All native service ports remain private or loopback edge-only. Runtime credentials come from OpenBao or approved secret files. TLS verification may not be disabled. Anonymous access, business writes, communications delivery, financial mutation, and trading authority remain prohibited.

## Evidence and milestone

Every authority record identifies its repository, exact ref, exact source SHA, source PR, exact-head result, review-evidence state, and source-only activation state.

The positive milestone is:

`CODESTRA_OBSERVABILITY_SOURCE_COMPATIBILITY_READY_FOR_STAGING_PREPARATION`

It remains false while any authority is outside `test`, any exact-head result is not successful, or any review-evidence record is pending or has unresolved threads.

This source gate does not install services, build or publish images, change DNS, start containers, apply Caddy or firewall changes, dispatch Keycloak apply, generate client secrets, initialize or unseal OpenBao, activate telemetry, deliver alerts, or carry production traffic.
