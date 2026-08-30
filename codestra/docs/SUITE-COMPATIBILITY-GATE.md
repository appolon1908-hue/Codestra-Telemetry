# Codestra Corporate Suite Compatibility Gate

## Purpose

This gate is the cross-repository source contract for the twelve approved Codestra observability, analytics, and security products:

1. Loki
2. Prometheus
3. Grafana
4. Tempo
5. OpenTelemetry Collector
6. Alloy
7. Node Exporter
8. cAdvisor
9. Redis Exporter
10. Blackbox Exporter
11. Superset
12. OpenBao

It does not own those products, deploy them, replace their repository-local validation, or create a thirteenth runtime. It proves that their independently reviewed source contracts describe one coherent Codestra corporate platform.

## Corporate business catalogue

The exact business identifiers are:

```text
codestra
moneybee
beyvra
breero
larim-a
transportation
booked4seasons
social
klyrow
telnexa
kyqra
restaurant
provisioning
```

These values are stable machine identifiers. Display names may be localized in Grafana or Superset, but telemetry, tenancy, policy, and release evidence use the canonical identifiers.

## Canonical dimensions

Only the following portfolio dimensions are mandatory across metrics, logs, traces, dashboards, and source evidence:

```text
codestra_business
application
service
environment
server
region
deployment
```

Customer, tenant, user, email, phone, request, trace, message, order, payment, database statement, URL, container ID, pod UID, and financial transaction identifiers are not metric labels or log-stream labels. Correlation identifiers may be retained only as protected structured fields where the owning privacy contract permits them.

## Authority boundaries

| Product | Source authority | Corporate responsibility |
|---|---|---|
| Loki | `Codestra-Loki` | Business-isolated log storage, search, retention, and query limits |
| Prometheus | `Codestra-Prometheus` | Metrics scraping, recording rules, SLI/SLO calculations, and alert evaluation |
| Grafana | `Codestra-Grafana-` | Read-only operational presentation and metrics/logs/traces correlation |
| Tempo | `Codestra-Tempo` | Business-isolated trace storage, search, service graphs, and span metrics |
| OpenTelemetry | `Codestra-Telemetry` | OTLP ingress, normalization, redaction, tail sampling, and backend routing |
| Alloy | `Codestra-Alloy` | Host/service log collection and bounded forwarding to approved backends |
| Node Exporter | `Codestra-Node-Exporter` | Host metrics and controlled operational-evidence textfiles |
| cAdvisor | `Codestra-cAdvisor` | Container resource metrics through a read-only Docker metadata boundary |
| Redis Exporter | `Codestra-Redis-Exporter` | Read-only aggregate Redis health, capacity, replication, and persistence metrics |
| Blackbox Exporter | `Codestra-Blackbox-Exporter` | Synthetic HTTPS, TLS, DNS, TCP, ICMP, and approved gRPC evidence |
| Superset | `Superset` | Certified read-only management datasets, RLS, and executive analytics |
| OpenBao | `Codestra-OpenBao` | Short-lived secrets, workload identity, PKI, dynamic credentials, transit, and audit |

No component may absorb another component's authority merely because it can technically implement a similar feature.

## Approved data flows

```text
Alloy --------------------------> Loki
Applications / SDKs -----------> OpenTelemetry
OpenTelemetry -----------------> Prometheus, Loki, Tempo
Node Exporter -----------------> Prometheus
cAdvisor ----------------------> Prometheus
Redis Exporter ----------------> Prometheus
Blackbox Exporter -------------> Prometheus
Prometheus + Loki + Tempo -----> Grafana
Certified read-only datasets --> Superset
OpenBao -----------------------> short-lived identity, certificates, and runtime secret delivery
```

Prometheus remains authoritative for metrics retention, recording rules, SLOs, and alert evaluation. OpenTelemetry may expose sanitized application metrics to Prometheus but does not become a second metrics authority. Grafana does not deliver communications or own alert routing. Superset does not query production transaction databases with write-capable credentials. OpenBao does not become a general application workflow engine.

## Business isolation

`codestra_business` is assigned by deployment-controlled identity. Callers cannot select or override another business.

- Loki and Tempo tenant identity must match the assigned Codestra business.
- OpenTelemetry and Alloy overwrite or remove caller-controlled business identity.
- Prometheus labels are normalized from reviewed target metadata and relabel rules.
- Grafana business access remains disabled until datasource-level or organization-level isolation and negative cross-business tests are proven; folder permissions alone are insufficient.
- Superset business access remains disabled until database-native RLS, Superset RLS, certified dataset grants, and negative cross-business tests are proven together.
- OpenBao policies are scoped by business, application, and environment; cross-business wildcards are prohibited.

## Corporate security invariants

Every repository-local runtime candidate must preserve the controls relevant to that product:

- native administration and ingestion endpoints are private;
- public native host-port publication is prohibited;
- immutable digest-bearing image inputs are required;
- secret material and usable private keys are prohibited in Git;
- runtime credentials come from OpenBao or approved secret files;
- mTLS and CA verification protect collector/backend and exporter/scraper boundaries where specified;
- anonymous access and insecure verification are disabled;
- root filesystems are read-only where product compatibility permits;
- Linux capabilities are dropped, `no-new-privileges` is enabled, and resources are bounded;
- log, metric, and trace attributes are minimized before export;
- all live delivery, dialing, publishing, lender, Odoo, provider, and trading capabilities remain outside this suite.

## Beyvra financial boundary

The suite may observe safe aggregate health, latency, market-data freshness, reconciliation state, dependency health, risk-control state, and non-authoritative operational events. It cannot receive broker/exchange/custody signing material, authorize or sign trades, decrypt protected trading payloads, mutate the authoritative ledger, or provide a backdoor around Beyvra's application control plane.

## Source-evidence model

The manifest records one exact source head per authority. Repository-local checks remain authoritative for implementation correctness. The suite gate verifies that:

1. all twelve authorities are unique and use approved canonical hosts;
2. the business catalogue and canonical dimensions are exact;
3. source heads are full Git SHAs and their recorded validation state is successful before the milestone can be achieved;
4. approved data-flow edges do not create an ownership bypass;
5. business, privacy, mTLS, immutable-release, and financial boundaries are represented consistently;
6. every activation field remains false;
7. unresolved review evidence blocks the milestone;
8. source promotion is not described as deployment or production activation.

GitHub check results and review-thread state must be reverified against each exact head whenever any authority head changes. A green suite-manifest workflow cannot substitute for repository-local exact-head checks.

## Milestone

The only positive source milestone emitted by this gate is:

```text
CODESTRA_CORPORATE_SUITE_SOURCE_READY_FOR_STAGING_REVIEW
```

It means the twelve source authorities are compatible and ready for a separate staging review. It never means:

```text
DEPLOYED
PRODUCTION_READY
RUNTIME_ACTIVATED
```

## Non-deployment rule

This gate creates files, validation, and review evidence only. It does not merge product PRs, deploy containers, create networks, install certificates or secrets, alter DNS/Caddy/Kong/Keycloak, activate probes or scrapes, ingest production telemetry, send communications, run business workflows, mutate customer data, or grant financial authority.
