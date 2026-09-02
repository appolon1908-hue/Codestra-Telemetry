# Codestra Telemetry

This repository is the source authority for two private observability
workloads:

- the Codestra OpenTelemetry Collector, derived from the official Collector
  Contrib 0.159.0 image with repository-owned mTLS, identity, redaction,
  sampling, queue, retry, and routing configuration;
- the read-only Codestra observability control API, which exposes bounded
  health, readiness, topology, contract, and immutable-release readback for the
  fourteen observability authorities.

The imported `open-telemetry/opentelemetry-collector` source snapshot under
`upstream/` is attribution and review evidence. It is not the executable image
authority; `codestra/release/runtime-base.lock.json` pins the accepted Contrib
release and platform manifest. Codestra-owned code and configuration live under
`codestra/`.

## Repository state

- Exposure: private networks only; no public native ports or edge route.
- Collector health: `GET /` on private port `13133`.
- Control API health/readiness: `GET /healthz` and `GET /readyz` on private port
  `8090`; all management reads require the mounted bearer identity.
- Promotion: `development -> test -> staging -> production -> main`.
- Artifact model: separate signed Model A images for the Collector and control
  API, built only from a protected production SHA.
- Runtime status: `SOURCE_PREPARED_NOT_DEPLOYED`.
- Production activation: not authorized by repository merge or release.

## Local source validation

```bash
python3 -m pip install -r requirements-validation.txt
python3 scripts/validate_repository_authority.py
python3 scripts/validate_codestra_collector.py
python3 scripts/validate_collector_image_readiness.py
python3 scripts/validate_codestra_control_api.py
python3 scripts/validate_control_api_image_readiness.py
(cd codestra/control-api && go test ./...)
```

These commands validate repository source only. They do not connect to a
server, production network, OpenBao, Keycloak, SMTP, or a provider.
