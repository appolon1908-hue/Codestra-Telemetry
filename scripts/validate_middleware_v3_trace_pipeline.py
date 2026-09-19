#!/usr/bin/env python3
"""Fail-closed proof of the Middleware V3 trace pipeline: propagation preserved, credentials scrubbed.

Replays the agent's ``attributes/redact`` key patterns and the OTTL
``replace_all_patterns`` / ``replace_pattern`` statements of ``transform/secret_shaped``
over a corpus of attribute names, attribute values and log bodies that plant one
credential of every class named by the Lane E contract. Proves that no planted
value survives, that drilldown attributes (correlation.id, codestra.operation.id,
openbao.secret_ref, deployment.id) are never deleted or damaged, that the collector
never rewrites W3C trace context, and that
``codestra/contracts/middleware-v3-trace-pipeline.v1.json`` stays dark, pinned and
consistent with the configuration. PyYAML is the only dependency (already pinned).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CODESTRA = ROOT / "codestra"
AGENT = CODESTRA / "collector-agent.yaml"
GATEWAY = CODESTRA / "collector.yaml"
CONTRACT = CODESTRA / "contracts" / "middleware-v3-trace-pipeline.v1.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
STATEMENT_RE = re.compile(
    r'^(replace_all_patterns|replace_pattern)\((attributes,\s*"value"|body),\s*"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"\)$'
)
V3_STAGES = ["http_ingress", "jwt_auth", "policy_engine", "safety_gate", "db_transaction", "outbox", "worker_lease", "adapter_execution", "provider_readback", "reconciliation"]

DELETED_KEYS = [
    "authorization", "cookie", "set-cookie", "password", "api_key", "x-api-key", "client_secret", "access_token",
    "smtp_password", "db_password", "redis_password", "postgres_password", "provider_api_key", "telnexa_api_key",
    "bao_token", "openbao_token", "vault_token", "x-vault-token", "aws_secret_access_key", "klyrow_client_secret",
    "service_account_credentials", "provider_credentials", "postgres_dsn", "database_url", "smtp_connection_string",
    "webhook_signing_secret", "private_key", "db.statement", "http.request.header.x-api-key", "email", "phone",
]
KEPT_KEYS = [
    "correlation.id", "codestra.operation.id", "openbao.secret_ref", "openbao.secret_class", "codestra.token_type",
    "deployment.id", "service.name", "codestra.command_family", "codestra.adapter", "codestra.policy.result",
    "http.route", "http.response.status_code", "codestra.lease.outcome", "codestra.token_count", "idempotency_key_hash",
]
VALUE_CORPUS: list[tuple[str, list[str], list[str]]] = [
    ("Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJtaWRkbGV3YXJlIn0.c2lnbmF0dXJlLXNpZ25hdHVyZQ", ["eyJhbGciOiJSUzI1NiJ9"], []),
    ("Basic dXNlcjpwYXNzd29yZC12YWx1ZQ==", ["dXNlcjpwYXNzd29yZC12YWx1ZQ=="], []),
    ("postgres://mw:DbPassw0rd@postgres:5432/mw", ["DbPassw0rd"], ["postgres:5432"]),
    ("redis://:RedisPassw0rd@redis:6379/0", ["RedisPassw0rd"], ["redis:6379"]),
    ("smtp://mailer:S3cr3tSMTPpass@smtp.internal:587", ["S3cr3tSMTPpass"], ["smtp.internal"]),
    ("hvs.CAESIabcdefghijklmnopqrstuvwxyz0123456789ABC", ["hvs.CAESI"], []),
    ("hvb.AAAAAQJbatchtokenvalue0123456789abcdefghij", ["hvb.AAAAAQJ"], []),
    ("s.abcdefghijklmnopqrstuvwxyz1234", ["s.abcdefghijklmnopqrstuvwxyz1234"], []),
    ("b." + "x" * 70, ["b." + "x" * 70], []),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----", ["MIIEowIBAAKCAQEA"], []),
    ("codestra/production/middleware/api/database", [], ["codestra/production/middleware/api/database"]),
    ("corr-42 op-777 22d023a9c65b", [], ["corr-42", "op-777", "22d023a9c65b"]),
]
BODY_CORPUS: list[tuple[str, list[str], list[str]]] = VALUE_CORPUS + [
    ("SMTP_PASSWORD=S3cr3tSMTPpass SMTP_HOST=smtp.internal", ["S3cr3tSMTPpass"], ["smtp.internal"]),
    ("provider_api_key=sk_live_PROVIDERKEY1234567890 provider=klyrow", ["sk_live_PROVIDERKEY1234567890"], ["klyrow"]),
    ("db_password: DbPassw0rd host: postgres", ["DbPassw0rd"], ["postgres"]),
    ("client_secret=kc-client-secret-value-123 client_id=middleware-api", ["kc-client-secret-value-123"], ["middleware-api"]),
    ("openbao_token=s.abcdefghijklmnopqrstuvwxyz1234 operation_id=op-1", ["s.abcdefghijklmnopqrstuvwxyz1234"], ["op-1"]),
    ("X-Vault-Token: hvs.CAESIabcdefghijklmnopqrstuvwxyz0123456789ABC", ["hvs.CAESI"], []),
    ("secret_ref=codestra/production/middleware/api/database token_count=3 lease_id_hash=sha256:abc", [], ["codestra/production/middleware/api/database", "3", "sha256:abc"]),
]


def fail(message: str) -> None:
    print(f"MIDDLEWARE_V3_TRACE_PIPELINE_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> Any:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def ottl_string(raw: str) -> str:
    """Undo OTTL string escapes and confmap $$ escaping."""
    return raw.replace("\\\\", "\\").replace('\\"', '"').replace("$$", "$")


def to_python_replacement(replacement: str) -> str:
    return re.sub(r"\$(\d+)", r"\\\1", replacement.replace("\\", "\\\\"))


def compile_pattern(expression: str) -> re.Pattern[str]:
    if re.search(r"\(\?[=!<]|\\[1-9]", expression):
        fail(f"pattern leaves the RE2/Python common subset: {expression[:60]}")
    try:
        return re.compile(expression)
    except re.error as exc:
        fail(f"pattern does not compile: {expression[:60]}: {exc}")
    return re.compile("")


def key_patterns(config: dict[str, Any]) -> list[re.Pattern[str]]:
    actions = config.get("processors", {}).get("attributes/redact", {}).get("actions", [])
    patterns = [compile_pattern(a["pattern"]) for a in actions if a.get("action") == "delete" and "pattern" in a]
    if not patterns:
        fail("attributes/redact has no delete patterns")
    return patterns


def statements(config: dict[str, Any], signal: str) -> list[tuple[str, str, re.Pattern[str], str]]:
    """(function, target, pattern, replacement) for the secret_shaped statements of one signal."""
    processor = config.get("processors", {}).get("transform/secret_shaped", {})
    result = []
    for group in processor.get(f"{signal}_statements", []):
        for statement in group.get("statements", []):
            match = STATEMENT_RE.match(statement.strip())
            if not match:
                fail(f"unrecognised secret_shaped statement: {statement[:80]}")
            function, target, pattern, replacement = match.groups()
            result.append((function, "body" if target == "body" else "value", compile_pattern(ottl_string(pattern)), ottl_string(replacement)))
    if not result:
        fail(f"transform/secret_shaped has no {signal} statements")
    return result


def scrub(text: str, rules: list[tuple[str, str, re.Pattern[str], str]], target: str) -> str:
    for _, rule_target, pattern, replacement in rules:
        if rule_target == target:
            text = pattern.sub(to_python_replacement(replacement), text)
    return text


def validate_keys(patterns: list[re.Pattern[str]]) -> None:
    for key in DELETED_KEYS:
        if not any(p.search(key) for p in patterns):
            fail(f"attribute key {key} would survive attributes/redact")
    for key in KEPT_KEYS:
        if any(p.search(key) for p in patterns):
            fail(f"drilldown attribute key {key} would be deleted by attributes/redact")


def validate_values(config: dict[str, Any]) -> None:
    for signal in ("trace", "log"):
        rules = statements(config, signal)
        for value, secrets, kept in VALUE_CORPUS:
            result = scrub(value, rules, "value")
            for secret in secrets:
                if secret in result:
                    fail(f"{signal} attribute value leaked {secret!r}: {result!r}")
            for keep in kept:
                if keep not in result:
                    fail(f"{signal} attribute value damaged {keep!r}: {result!r}")
        if signal == "log":
            for body, secrets, kept in BODY_CORPUS:
                result = scrub(body, rules, "body")
                for secret in secrets:
                    if secret in result:
                        fail(f"log body leaked {secret!r}: {result!r}")
                for keep in kept:
                    if keep not in result:
                        fail(f"log body damaged {keep!r}: {result!r}")


def validate_propagation(agent: dict[str, Any], gateway: dict[str, Any]) -> None:
    for name, config in (("agent", agent), ("gateway", gateway)):
        rendered = json.dumps(config.get("processors", {}))
        if re.search(r'set\((trace_id|span_id|parent_span_id)\b', rendered):
            fail(f"{name} rewrites W3C trace context")
        if re.search(r'delete_key\(attributes,\s*"(correlation\.id|codestra\.operation\.id)"', rendered):
            fail(f"{name} deletes a drilldown identifier")
    if agent.get("receivers", {}).get("otlp", {}).get("protocols", {}).get("grpc", {}).get("endpoint") != "127.0.0.1:4317":
        fail("agent OTLP gRPC must bind loopback")
    pipelines = agent.get("service", {}).get("pipelines", {})
    for signal in ("traces", "logs"):
        processors = pipelines.get(signal, {}).get("processors", [])
        if processors[:1] != ["memory_limiter"] or "attributes/redact" not in processors or "transform/secret_shaped" not in processors:
            fail(f"agent {signal} pipeline must bound memory, redact keys and scrub values")
        if processors.index("attributes/redact") > processors.index("transform/secret_shaped"):
            fail(f"agent {signal} pipeline must delete keys before scrubbing values")
    correlation = gateway.get("processors", {}).get("transform/correlation", {})
    if "correlation.id" not in json.dumps(correlation) or ", 0, 128)" not in json.dumps(correlation):
        fail("gateway must normalise and bound correlation.id")


def validate_contract(contract: dict[str, Any], agent: dict[str, Any]) -> None:
    if contract.get("contract_id") != "middleware-v3-trace-pipeline" or contract.get("status") != "PREPARED_DISABLED":
        fail("contract identity or status drift")
    if contract.get("activation_enabled") is not False:
        fail("activation_enabled must be false")
    middleware = contract.get("middleware", {})
    if not SHA40.fullmatch(str(middleware.get("prep_base_sha", ""))):
        fail("middleware.prep_base_sha must be a 40-hex commit")
    if middleware.get("v3_final_sha") != "PENDING" and not SHA40.fullmatch(str(middleware.get("v3_final_sha"))):
        fail("middleware.v3_final_sha must be PENDING or a 40-hex commit")
    if contract.get("propagation", {}).get("headers") != ["traceparent", "tracestate"]:
        fail("propagation must preserve traceparent and tracestate")
    stages = [span.get("stage") for span in contract.get("v3_span_coverage", [])]
    if stages != V3_STAGES:
        fail(f"span coverage must list exactly {V3_STAGES}")
    forbidden = set(contract.get("forbidden_span_attributes", []))
    patterns = key_patterns(agent)
    for span in contract["v3_span_coverage"]:
        if span.get("status") != "EXPECTED_PENDING_V3":
            fail(f"{span['stage']}: every V3 span is EXPECTED_PENDING_V3")
        for attribute in span.get("attributes", []):
            if attribute in forbidden or any(p.search(attribute) for p in patterns):
                fail(f"{span['stage']}: attribute {attribute} is forbidden or would be redacted")
    for key in ("authorization", "password", "client_secret", "db.statement", "email", "phone", "customer_id", "command_payload", "secret_value"):
        if key not in forbidden:
            fail(f"forbidden span attribute {key} must be declared")
    fields = contract.get("required_common_fields", {})
    for field in ("service_id", "environment", "deployment_sha", "correlation_id", "operation_id", "trace_id"):
        if field not in fields:
            fail(f"required common field {field} missing")


def main() -> None:
    agent = load_yaml(AGENT)
    gateway = load_yaml(GATEWAY)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validate_keys(key_patterns(agent))
    validate_values(agent)
    validate_propagation(agent, gateway)
    validate_contract(contract, agent)
    print(
        "MIDDLEWARE_V3_TRACE_PIPELINE=PASS TRACE_REDACTION=PASS "
        f"prep_base={contract['middleware']['prep_base_sha'][:12]} v3_final={contract['middleware']['v3_final_sha']} "
        f"spans={len(contract['v3_span_coverage'])}"
    )


if __name__ == "__main__":
    main()
