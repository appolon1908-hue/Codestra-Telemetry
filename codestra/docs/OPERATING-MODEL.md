# Codestra OpenTelemetry Collector Operating Model

## Authority

The Collector owns telemetry ingress, business identity enforcement, normalization, redaction, tail sampling, bounded buffering and routing. Prometheus owns metrics and SLOs, Tempo owns traces, Loki owns logs, Grafana owns presentation, Alertmanager owns incident routing, Keycloak owns human identity and OpenBao owns secrets and PKI.

## Deployment unit

One Collector instance is deployed for one approved Codestra business, environment, region and server boundary. Its deployment inputs establish the trusted business identity. Workloads may identify their application, service, version and deployment, but they cannot select a different business tenant.

The instance connects to:

1. one business-isolated ingress network;
2. the shared private observability backend network;
3. no public host port and no host network.

OTLP ingress requires mutual TLS. Certificate issuance, rotation and revocation belong to the approved PKI authority. The Collector never stores private-key values in Git.

## Pipeline order

For each signal the operating order is:

1. receive over governed OTLP;
2. apply memory limits;
3. overwrite trusted business/environment/region/server identity;
4. remove sensitive resource and signal attributes;
5. reject missing application/service/version/deployment identity;
6. normalize metrics to corporate labels;
7. tail-sample traces after redaction;
8. batch and export;
9. persist temporary exporter backlog in bounded file storage.

Changing this order requires a reviewed compatibility and privacy analysis.

## Backpressure and outage behavior

The memory limiter protects the Collector process. Tempo and Loki exporters use persistent queues and bounded retry windows. Operators monitor queue size, enqueue failures, refused telemetry, send failures, process memory, CPU and dropped data.

When a backend outage exceeds the queue or retry budget, telemetry can be lost. The Collector must emit visible self-metrics and logs; it must never block or mutate a customer business transaction to preserve observability data.

## Sampling governance

Tail sampling preserves errors, slow traces and explicitly prioritized security, reconciliation, capability, financial and delivery paths. Ten-percent routine success sampling is an initial default. Changes require traffic evidence, storage-cost analysis, incident reconstruction tests and comparison of pre/post sampling coverage.

Head sampling inside applications must not independently discard the critical paths the Collector is required to preserve.

## Privacy and data minimization

Applications remain responsible for avoiding raw secrets and payloads at instrumentation time. The Collector provides defense-in-depth deletion, not permission to instrument sensitive data.

Release evidence must include representative fixtures proving removal of authorization data, cookies, credentials, personal identifiers, database statements, raw request/response bodies, and broker/exchange signing material. Customer or person identifiers cannot become Prometheus labels, Tempo tenant IDs or Loki stream labels.

## Storage and recovery

The writable Collector volume contains only file-backed exporter queue state. It is not long-term telemetry storage. Staging must prove:

- restart recovery of queued traces and logs;
- bounded disk growth during backend unavailability;
- queue drain after backend recovery;
- correct behavior when the queue reaches capacity;
- no cross-business queue reuse;
- deletion of stale queue state during intentional business reassignment.

## Service objectives

Initial engineering objectives, pending staging calibration:

- OTLP ingress availability of at least 99.9% for the approved deployment topology;
- zero public OTLP listeners;
- zero unapproved cross-business ingestion or export;
- zero known credentials or customer payloads exported;
- visible self-metrics for refused, dropped, queued and failed telemetry;
- trace/log exporter queues below 80% during normal operation;
- Collector p95 processing latency below one second during expected peak traffic;
- successful recovery from a 15-minute Tempo or Loki outage without unreported loss.

## Release evidence

Production promotion requires:

- immutable builder, upstream and final image digests;
- software bill of materials and vulnerability review;
- Collector native configuration validation;
- mTLS certificate-chain and revocation tests;
- business allowlist and cross-business denial tests;
- required resource-identity fixtures;
- privacy/redaction fixtures;
- tail-sampling coverage tests;
- queue durability and capacity tests;
- Prometheus, Tempo and Loki connectivity tests;
- rollback instructions and previous-image digest;
- human approval.

Promotion order is `feature/* -> development -> test -> staging -> production -> main`. All source configuration remains `CONFIG_PREPARED_NOT_DEPLOYED` until the evidence package is approved.
