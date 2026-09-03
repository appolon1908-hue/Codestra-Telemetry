# Codestra Observability 14-Authority Repository Handoff

## Server placement

```text
CENTRAL_STACK_INSTALL_HOST=37.27.128.39
CORE_APPLICATION_HOST=65.109.65.169
CENTRAL_AUTHORITY_ON_CORE_HOST=NO
SSH_CONFIGURATION_CHANGES_AUTHORIZED=NO
ADMIN_BYPASS_AUTHORIZED=NO
```

The central host placement is Prometheus, Grafana, Alertmanager, Loki, Tempo, Blackbox Exporter, Superset, OpenBao, the observability control API, and a central OpenTelemetry receiver when required. The core application host placement is Alloy, an OpenTelemetry Collector agent, Node Exporter, cAdvisor, Redis Exporter, and PostgreSQL Exporter. Prometheus, Grafana, Loki, Tempo, Superset, and OpenBao remain central authorities and are not duplicated on the core application host.

This repository handoff does not authorize either placement. The later server mission may install only artifacts already verified in the canonical source lock and production BOM.

## Repository-owned production/API contracts

| Component | Repository | Contract PR |
|---|---|---:|
| Loki | `appolon1908-hue/Codestra-Loki` | #18 |
| Prometheus | `appolon1908-hue/Codestra-Prometheus` | #30 |
| Grafana | `appolon1908-hue/Codestra-Grafana-` | #18 |
| Tempo | `appolon1908-hue/Codestra-Tempo` | #16 |
| OpenTelemetry | `appolon1908-hue/Codestra-Telemetry` | #18 |
| Alloy | `appolon1908-hue/Codestra-Alloy` | #18 |
| Node Exporter | `appolon1908-hue/Codestra-Node-Exporter` | #22 |
| cAdvisor | `appolon1908-hue/Codestra-cAdvisor` | #19 |
| Redis Exporter | `appolon1908-hue/Codestra-Redis-Exporter` | #19 |
| PostgreSQL Exporter | `appolon1908-hue/Codestra-Postgres-Exporter` | #7 |
| Blackbox Exporter | `appolon1908-hue/Codestra-Blackbox-Exporter` | #19 |
| Alertmanager | `appolon1908-hue/Codestra-Alertmanager` | #6 |
| Superset | `appolon1908-hue/Superset` | #18 |
| OpenBao | `appolon1908-hue/Codestra-OpenBao` | #33 |

Each repository owns its native API surface, authentication and authorization boundary, business isolation, image construction, tests, release evidence, backup/recovery, and rollback. The handoff does not create a thirteenth runtime or a duplicate API gateway.

## Promotion path

```text
review branch
  -> development
  -> test
  -> staging
  -> production
```

At every transition require:

```text
EXACT_HEAD_CI=PASS
INDEPENDENT_REVIEW=PASS
UNRESOLVED_REVIEW_THREADS=0
CHANGES_REQUESTED=0
MERGEABLE=YES
ADMIN_BYPASS_USED=NO
```

Any new commit invalidates approval for the prior head. Do not deploy from a review, remediation, development, test, or staging branch. Build and sign production artifacts only from the protected production SHA.

## Installation gate

Before Codex connects to `37.27.128.39`, require:

```text
REPOSITORIES_READY=14/14
PRODUCTION_BRANCHES_RECONCILED=14/14
SOURCE_LOCK=PASS
IMMUTABLE_IMAGES=PASS
SIGNED_RELEASES=PASS
SBOMS=PASS
PROVENANCE=PASS
VULNERABILITY_GATES=PASS
EXACT_DIGEST_COMPOSE=PASS
ROLLBACK_MANIFEST=PASS
SERVER_INSTALL_AUTHORIZED=YES
```

A workflow `startup_failure`, zero allocated jobs, billing/spending-limit error, absent required check, pending check, or failed check blocks the affected promotion or installation. Local tests do not replace required GitHub exact-head CI.

## Runtime API certification

The server mission must prove all repository-defined routes and protocols without inventing duplicate product APIs. For every required endpoint or protocol prove route existence, verified TLS, intended authentication, wrong-role denial, wrong-business denial where applicable, timeout and concurrency controls, zero sensitive output, zero unexpected `404`, zero unexpected `5xx`, exact source SHA, and exact image digest.

Protected endpoints may correctly return redirects, `401`, `403`, `405`, `415`, `422`, or `429`; the expected response must match the component contract.

## OpenBao blocking condition

The current OpenBao source-only VEX for `CVE-2026-84304` applies only while all deployment and runtime-binding authorities remain false. The pinned image contains affected `google.golang.org/grpc` v1.82.1, and the disposition expires September 9, 2026.

OpenBao staging runtime, production canary, and production activation remain prohibited until:

```text
GRPC_GO_VERSION>=1.83.1
```

or a new, non-expired, evidence-backed assessment authorizes the exact image and runtime configuration.

## Repository-first defect handling

When installation exposes a defect:

1. stop the affected wave;
2. preserve the previous healthy workload;
3. reproduce the defect;
4. fix the owning GitHub repository;
5. add a regression test;
6. commit and push;
7. obtain exact-head CI and review;
8. merge through protection;
9. build and sign a new immutable artifact;
10. update the BOM and rollback manifest;
11. pull the protected production SHA and retry.

Never patch production in place and leave GitHub behind.

## Safety

This handoff is source documentation only. It does not deploy containers, initialize or unseal OpenBao, issue credentials or certificates, change SSH, alter DNS/Caddy/Keycloak/Kong, activate telemetry, enable business writes, deliver communications, call providers, or grant lending/payment/trading authority.
