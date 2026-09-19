# Middleware V3 trace pipeline (Lane E preparation)

Status: **PREPARED_DISABLED**. `MIDDLEWARE_PREP_BASE=22d023a9c65b0789a0f7ee6c28548753521a9eff`,
`V3_FINAL_SHA=PENDING`.

## Path

Middleware OTel SDK -> per-host agent (`codestra/collector-agent.yaml`, OTLP on
127.0.0.1:4317/4318 only) -> central gateway (`codestra/collector.yaml`, mutual TLS) ->
Tempo (traces), Loki (logs), Prometheus (metrics).

## Contract (`codestra/contracts/middleware-v3-trace-pipeline.v1.json`)

* **Propagation**: W3C `traceparent` / `tracestate` preserved end to end; the collector never
  rewrites trace context; `X-Correlation-ID` becomes a bounded `correlation.id`; asynchronous
  hops use span links.
* **Common fields**: `service.name`, `deployment.environment.name`, `deployment.id`
  (deployment sha), `correlation.id`, `codestra.operation.id`, native trace context.
* **V3 span coverage** (all `EXPECTED_PENDING_V3`): HTTP ingress, JWT/auth, Policy Engine,
  Safety Gate, DB transaction, outbox, worker lease, adapter execution, provider readback,
  reconciliation - each with a closed low-cardinality attribute set and no credential,
  statement, payload or personal attribute.
* **Redaction**: attribute keys are deleted by exact name and, new in this change, by
  suffix (`smtp_password`, `db_password`, `provider_api_key`, `x-api-key`, `bao_token`,
  `aws_secret_access_key`, `*_client_secret`, `*_credentials`, `*_dsn`,
  `*_connection_string`); values and log bodies are scrubbed for Bearer and Basic
  credentials, `hvs.`/`hvb.`/`s.`/`b.` OpenBao tokens, JWT shapes, PEM private keys,
  `user:password@` in connection URLs and `key=value` credential pairs. PEM scrubbing now
  also covers log attribute values (previously spans and bodies only). `correlation.id`,
  `codestra.operation.id`, `openbao.secret_ref` and `deployment.id` are never touched.

## Proof

`scripts/validate_middleware_v3_trace_pipeline.py` replays the agent's key patterns and
OTTL statements over a planted-credential corpus (**TRACE_REDACTION=PASS**), proves the
collector never sets trace context fields, and checks the contract for drift.
`tests/test_middleware_v3_trace_pipeline.py` adds targeted cases. Both run in
`validate-codestra-collector.yml`; the locked `otelcol-contrib validate` step still checks the
configuration itself.
