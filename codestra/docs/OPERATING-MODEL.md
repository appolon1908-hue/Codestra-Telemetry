# Codestra OpenTelemetry Collector Operating Model

## Authority

The Collector owns telemetry ingress, business identity enforcement, normalization, redaction, tail sampling, bounded buffering and routing. Prometheus owns metrics and SLOs, Tempo owns traces, Loki owns logs, Grafana owns presentation, Alertmanager owns incident routing, Keycloak owns human identity and OpenBao owns secrets and PKI.

## Deployment unit

The deployment candidate in this repository is the platform Collector. Its business identity is fixed as `platform` in reviewed Compose source; neither a caller nor an environment file can select a different tenant. Workloads may identify their application, service, version and deployment, but they cannot select a different business tenant. A future business-specific instance requires its own reviewed source authority, release evidence and isolated queue volume.

The instance connects to:

1. one business-isolated ingress network;
2. the shared private observability backend network;
3. no public host port and no host network.

OTLP ingress requires mutual TLS. Tempo and Loki exporter connections verify the approved backend CA and canonical backend service name. Certificate issuance, rotation and revocation belong to the approved PKI authority. The Collector never stores private-key values in Git.

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

The writable Collector volume contains only file-backed exporter queue state. Its external volume name is fixed as `codestra-platform-otelcol-storage`, preventing a deployment input from redirecting the platform Collector to another business queue. It is not long-term telemetry storage. Staging must prove:

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

## Local agent, central gateway and correlation (2026-09-16)

- `codestra/collector-agent.yaml` is the per-host OpenTelemetry Collector agent: applications send OTLP to `127.0.0.1:4318` (`/v1/traces`, `/v1/metrics`, `/v1/logs`) or gRPC `127.0.0.1:4317`; the agent redacts credentials, cookies, keys, JWT/OpenBao-shaped values and personal contact data before anything leaves the host, buffers through a bounded file-backed queue, and forwards over mutual TLS to the central gateway only. It never exports to Tempo, Loki or Prometheus directly and never binds a non-loopback address. Alloy stays the log-file/journal agent (`opentelemetryOwnsApplicationOtlp` is unchanged).
- The gateway (`codestra/collector.yaml`) keeps `correlation.id` on spans and logs, normalised from `correlation_id` and bounded to 128 characters, so one TEST_SYN operation can be followed across Caddy -> Kong -> Middleware -> Odoo/N8N and joined to its Middleware incident. Metrics never carry it. W3C `traceparent`/`tracestate` remain intrinsic to spans.
- Every `/run/secrets/otelcol_*` file is the OpenBao agent rendering of a reference in `codestra/secret-references.v1.json` (identity `otel-gateway`); no credential is committed.
- Failure modes: gateway unreachable -> the agent queues within its bounded file storage and business traffic continues; Tempo or Loki unreachable -> the gateway retries within its bounded budget and export failures surface as `otelcol_exporter_send_failed_*` (alerted by Prometheus); Middleware unreachable -> telemetry paths are unaffected.
