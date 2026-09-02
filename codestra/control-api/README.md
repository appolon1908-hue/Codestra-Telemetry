# Codestra Observability Control API

This is the private, read-only discovery and read-back plane for the fourteen Codestra monitoring, analytics, telemetry, exporter, and secrets authorities.

It does **not** replace native Prometheus, Grafana, Alertmanager, Loki, Tempo, OpenTelemetry, Alloy, exporter, Superset, or OpenBao APIs. It standardizes how authorized operators and automation discover those authorities, check sanitized health/readiness, inspect the approved topology, locate service contracts, and verify immutable release identity.

## API

- `GET /healthz` — process liveness; no upstream call.
- `GET /readyz` — registry and control-token readiness; no upstream call.
- `GET /metrics` — control-plane metrics.
- `GET /openapi.json` — this API contract.
- `GET /api/v1/capabilities` — explicit read-only capability flags.
- `GET /api/v1/services` — sanitized service discovery.
- `GET /api/v1/services/{service}` — one service and release/contract metadata.
- `GET /api/v1/services/{service}/health` — bounded health and readiness probes.
- `GET /api/v1/health` — bounded concurrent aggregate probe.
- `GET /api/v1/topology` — approved non-mutating signal graph.
- `GET /api/v1/contracts` — per-repository service contract locations.
- `GET /api/v1/releases` — validated source SHA and image digest read-back.

Every non-health route requires a bearer token from `CODESTRA_CONTROL_API_BEARER_TOKEN_FILE` unless `CODESTRA_CONTROL_API_AUTH_MODE=disabled` is explicitly selected for isolated tests. Production ingress must remain private and authenticated through Caddy/Kong/Keycloak or mTLS as applicable.

## Runtime configuration

The registry contains only environment-variable names, repository identity, probe paths, accepted status codes, and non-secret topology metadata. Actual URLs, bearer-token files, CA files, client certificates, client keys, Git revisions, and image digests are runtime inputs.

The API:

- accepts only `GET`, `HEAD`, and `OPTIONS`;
- never proxies native query, ingestion, notification, dashboard mutation, credential issuance, or secret APIs;
- discards every upstream response body;
- returns bounded reason codes instead of raw transport errors;
- follows no redirects;
- propagates a validated or generated `X-Correlation-ID`;
- validates source revisions as 40 lowercase hexadecimal characters;
- validates image identities as `sha256:<64 lowercase hexadecimal characters>`;
- defaults to `127.0.0.1:8090` and required bearer authentication.

## Build

The Dockerfile intentionally has no mutable image defaults. Both `GO_BUILDER_IMAGE` and `RUNTIME_IMAGE` are locked as reviewed `name@sha256:<digest>` references in `release/image-build.v1.json`. The reusable release workflow can build, scan, attest, and sign only an exact protected `production` commit. The repository candidate remains disabled behind the `candidate-after-approval` profile and does not publish a host port.

`compose.candidate.yaml` is deploy-only: it cannot build an image, requires exact source and digest read-back values, mounts the bearer token from a file, drops all capabilities, and joins only the pre-existing private observability network. Repository readiness does not authorize release, promotion, routing, secrets delivery, or deployment.

Local validation:

```bash
go test ./...
go vet ./...
go build ./cmd/codestra-observability-api
python ../../scripts/validate_codestra_control_api.py
```
