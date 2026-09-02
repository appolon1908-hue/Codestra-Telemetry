# Repository Profile — Codestra Telemetry

## Authority

- Repository: `appolon1908-hue/Codestra-Telemetry`
- Upstream Collector source: `open-telemetry/opentelemetry-collector`, exact
  snapshot in `CODESTRA_UPSTREAM_LOCK.json`
- Accepted Collector distribution: Contrib `0.159.0`, exact image and linux/amd64
  manifest in `codestra/release/runtime-base.lock.json`
- Branch model: `development -> test -> staging -> production -> main`
- Exposure: `internal_private`
- Current verdict: `REPO_RELEASE_READY=BLOCKED` until protected production
  merges and two signed immutable OCI releases exist and are centrally locked

This repository owns the Codestra OpenTelemetry Collector configuration, the
fourteen-service schema and read-only control plane, and the reusable immutable
release authorities used by the observability suite.

## Build and runtime entrypoints

The Collector image is built from `codestra/deploy/Dockerfile`, embeds
`codestra/collector.yaml`, and runs `/otelcol-contrib` as `10001:10001`. The
control API image is built from `codestra/control-api/Dockerfile`, compiles
`cmd/codestra-observability-api`, and runs it as `65532:65532`. Both build
manifests pin every base by digest, use a digest-pinned Dockerfile frontend, and
retain `productionActivation=false`.

Canonical non-activating manifests are `codestra/compose.candidate.yaml` and
`codestra/control-api/compose.candidate.yaml`. Neither contains a build path,
host port, mutable image, secret value, or default-active service profile.

## Dependencies and consumers

Approved OTLP clients use mTLS over business-isolated private networks. The
Collector exports metrics for Prometheus scraping, traces to Tempo, and logs to
Loki. Grafana consumes the backends, not the Collector. The private control API
performs bounded read-only probes of all fourteen authorities and never proxies
native response bodies or mutation methods.

The repository does not own long-term metrics/log/trace storage, dashboards,
alert routing, human identity, secret custody, business writes, provider
delivery, or public telemetry ingestion.

## Health, readiness, and data safety

The Collector health extension is private on `13133`; its embedded loopback
health binary is the container check. The control API separates `/healthz` from
`/readyz`; readiness fails when required bearer-token-file authentication is
unavailable. Exact-head CI validates source, configuration, Go race tests,
image construction, embedded files, non-root users, and OCI revision labels.

Collector queue state is bounded, business-scoped, and persisted only to the
external `codestra-platform-otelcol-storage` volume. It is operational backlog,
not an authoritative telemetry archive. Repository policy removes secret and
personal attributes before export, bounds metric labels, and forbids raw
payloads. Secret material is referenced only through mounted files.

## Release, backup, and rollback

Each workload is released separately by the protected reusable Model A
workflow. It builds from the exact production head, scans source and image,
generates SBOM and provenance, signs with GitHub OIDC, verifies the exact digest
and OCI revision, then publishes the immutable human tag.

The control API is stateless. Collector backup and rollback preserve the queue
volume, exact configuration checksum, protected source SHA, current and previous
OCI digests, and non-secret secret-file names. Rollback uses the recorded prior
digest without rebuilding and must prove health plus queue compatibility before
traffic is restored. `docs/BACKUP_RESTORE_ROLLBACK.md` and `docs/UPGRADE.md` are
the canonical procedures.

Merging, promoting, or publishing does not start a workload, open a listener,
apply credentials, contact production, or authorize deployment.
