# Repository profile

This repository owns the Codestra OpenTelemetry Collector configuration, the fourteen-service schema and read-only control plane, and the reusable immutable release authorities used by the observability suite.

The control API and the repository-configured Collector are built into separate signed, digest-pinned images. The Collector candidate fixes its tenant identity to `platform`, embeds the reviewed configuration, and has no host build or public-port path. Production activation remains disabled. Promotion, release, secrets delivery, routing, and deployment require separate protected-environment evidence.
