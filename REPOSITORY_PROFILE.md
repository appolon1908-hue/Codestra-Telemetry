# Repository profile

This repository owns the Codestra OpenTelemetry Collector configuration, the fourteen-service schema and read-only control plane, and the reusable immutable release authorities used by the observability suite.

The control API is built from repository Go source into a signed digest-pinned image. Production activation remains disabled. Promotion, release, secrets delivery, routing, and deployment require separate protected-environment evidence.
