# Backup, restore, and rollback

The control API is stateless. Before deployment, capture its current image digest, configuration checksums, Compose manifest, mounted secret-file paths without their values, and registry/OpenAPI files.

The Collector's `codestra-platform-otelcol-storage` volume contains bounded exporter queues. Before changing it, capture the current image digest, embedded configuration checksum, volume identity, queue-health evidence, mounted TLS file paths without their contents, and an approved snapshot or restoration procedure. Never reuse this queue for another business identity.

Rollback uses the previous approved digest without rebuilding, preserves all volumes, renders Compose first, and performs a controlled `docker compose up -d`. Collector rollback must prove the prior image can read and drain the preserved queue before the new digest is restored. Never use `docker compose down -v`.

The rollback bundle must pair the prior protected source SHA with its canonical
OCI repository and digest. Startup is intentionally denied when that runtime
tuple differs from the source revision embedded in the prior image; bypassing
the Collector entrypoint or control API identity check is not an approved
rollback mechanism.

The rollback manifest must retain the prior pair of network-specific aliases
with its configuration checksum. Before selecting the prior digest, verify that
its OTLP receivers bind only to the business-ingress alias and its health and
metrics listeners bind only to the observability alias. A rollback that restores
the shared `otel-collector` alias or any `0.0.0.0` listener is unsafe; use a
forward fix instead.
