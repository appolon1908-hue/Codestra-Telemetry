#!/usr/bin/env python3
"""Validate the fourteen-authority Codestra suite compatibility contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "codestra" / "suite-contract.v2.json"
DOC = ROOT / "codestra" / "docs" / "SUITE-COMPATIBILITY-GATE-V2.md"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

BUSINESSES = [
    "codestra", "moneybee", "beyvra", "breero", "larim-a", "transportation",
    "booked4seasons", "social", "klyrow", "telnexa", "kyqra", "restaurant",
    "provisioning",
]
DIMENSIONS = [
    "codestra_business", "application", "service", "environment", "server",
    "region", "deployment",
]
FORBIDDEN_INDEXED = [
    "tenant_id", "customer_id", "user_id", "email", "phone", "request_id",
    "trace_id", "message_id", "order_id", "payment_id", "transaction_id",
    "db_statement", "raw_url", "container_id", "pod_uid",
]
AUTHORITIES = [
    ("grafana", "appolon1908-hue/Codestra-Grafana-", "graf.codestra.media", "read-only-operational-presentation-authority", "loopback_edge_only"),
    ("prometheus", "appolon1908-hue/Codestra-Prometheus", "prom.codestra.media", "metrics-slo-alert-evaluation-authority", "internal_private"),
    ("alertmanager", "appolon1908-hue/Codestra-Alertmanager", "aler.codestra.media", "middleware-governed-alert-routing-authority", "internal_private"),
    ("loki", "appolon1908-hue/Codestra-Loki", "loki.codestra.media", "central-log-authority", "internal_private"),
    ("tempo", "appolon1908-hue/Codestra-Tempo", "temp.codestra.media", "distributed-trace-authority", "internal_private"),
    ("opentelemetry", "appolon1908-hue/Codestra-Telemetry", "otel.codestra.media", "telemetry-ingress-normalization-redaction-routing-authority", "internal_private"),
    ("superset", "appolon1908-hue/Superset", "supe.codestra.media", "certified-read-only-business-analytics-authority", "loopback_edge_only"),
    ("node-exporter", "appolon1908-hue/Codestra-Node-Exporter", "node.codestra.media", "host-metrics-operational-evidence-authority", "internal_private"),
    ("cadvisor", "appolon1908-hue/Codestra-cAdvisor", "cadv.codestra.media", "container-resource-metrics-authority", "internal_private"),
    ("postgres-exporter", "appolon1908-hue/Codestra-Postgres-Exporter", "pgex.codestra.media", "postgresql-health-capacity-replication-metrics-authority", "internal_private"),
    ("redis-exporter", "appolon1908-hue/Codestra-Redis-Exporter", "rdex.codestra.media", "redis-health-capacity-persistence-metrics-authority", "internal_private"),
    ("blackbox-exporter", "appolon1908-hue/Codestra-Blackbox-Exporter", "blac.codestra.media", "synthetic-availability-dns-tls-authority", "internal_private"),
    ("alloy", "appolon1908-hue/Codestra-Alloy", "allo.codestra.media", "host-service-log-collection-agent-authority", "internal_private"),
    ("openbao", "appolon1908-hue/Codestra-OpenBao", "bao.codestra.media", "secrets-pki-workload-identity-authority", "private_strong_auth"),
]
EXPECTED_FLOWS = {
    ("alloy", "loki", "logs"),
    ("opentelemetry", "loki", "logs"),
    ("opentelemetry", "prometheus", "metrics"),
    ("opentelemetry", "tempo", "traces"),
    ("node-exporter", "prometheus", "metrics"),
    ("cadvisor", "prometheus", "metrics"),
    ("postgres-exporter", "prometheus", "metrics"),
    ("redis-exporter", "prometheus", "metrics"),
    ("blackbox-exporter", "prometheus", "metrics"),
    ("prometheus", "alertmanager", "alerts"),
    ("prometheus", "grafana", "metrics"),
    ("loki", "grafana", "logs"),
    ("tempo", "grafana", "traces"),
    ("certified-readonly-datasets", "superset", "analytics"),
    ("openbao", "suite-workloads", "identity-certificates-secrets"),
}
MILESTONE = "CODESTRA_OBSERVABILITY_SOURCE_COMPATIBILITY_READY_FOR_STAGING_PREPARATION"
PROHIBITED = ["DEPLOYED", "PRODUCTION_READY", "RUNTIME_ACTIVATED"]


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail("suite contract must contain an object")
    return value


def validate_authorities(contract: dict[str, Any]) -> bool:
    values = contract.get("authorities")
    if not isinstance(values, list) or len(values) != 14:
        fail("exactly fourteen authority records are required")
    if [item.get("component") for item in values] != [item[0] for item in AUTHORITIES]:
        fail("authority order or component set mismatch")
    if [item.get("sequence") for item in values] != list(range(1, 15)):
        fail("authority sequence must be 1 through 14")

    repositories: set[str] = set()
    hostnames: set[str] = set()
    ready = True
    for value, expected in zip(values, AUTHORITIES, strict=True):
        component, repository, hostname, role, exposure = expected
        for key, wanted in {
            "repository": repository,
            "canonicalHostname": hostname,
            "role": role,
            "nativeExposure": exposure,
        }.items():
            if value.get(key) != wanted:
                fail(f"{component}: {key} must be {wanted!r}")
        if repository in repositories or hostname in hostnames:
            fail(f"{component}: repository or hostname is duplicated")
        repositories.add(repository)
        hostnames.add(hostname)

        if not isinstance(value.get("sourcePr"), int) or value["sourcePr"] < 1:
            fail(f"{component}: sourcePr must be positive")
        if not SHA40.fullmatch(str(value.get("sourceHead", ""))):
            fail(f"{component}: sourceHead must be a full lowercase SHA")
        stage = value.get("sourceStage")
        ref = value.get("sourceRef")
        checks = value.get("exactHeadChecks")
        if stage not in {"test", "development", "feature-review"}:
            fail(f"{component}: invalid sourceStage")
        if not isinstance(ref, str) or not ref:
            fail(f"{component}: sourceRef is required")
        if stage == "test" and ref != "test":
            fail(f"{component}: test stage must use the test ref")
        if stage == "development" and ref != "development":
            fail(f"{component}: development stage must use the development ref")
        if stage == "feature-review" and ref in {"development", "test", "staging", "production", "main"}:
            fail(f"{component}: feature-review must identify its exact feature ref")
        if checks not in {"success", "pending", "failure"}:
            fail(f"{component}: invalid exactHeadChecks")
        if stage != "test" or checks != "success":
            ready = False

        review = value.get("reviewEvidence")
        if not isinstance(review, dict):
            fail(f"{component}: reviewEvidence must be an object")
        if review.get("state") == "complete":
            if review.get("unresolvedThreads") != 0:
                fail(f"{component}: complete review evidence requires zero unresolved threads")
        elif review.get("state") == "pending":
            if review.get("unresolvedThreads") is not None:
                fail(f"{component}: pending review evidence requires null unresolvedThreads")
            ready = False
        else:
            fail(f"{component}: invalid review evidence state")

        if value.get("sourceOnlyStatus") != "CONFIG_PREPARED_NOT_DEPLOYED":
            fail(f"{component}: source-only status mismatch")
        if value.get("activationClaim") is not False:
            fail(f"{component}: activationClaim must be false")
        if value.get("businessScope") != "canonical-suite-catalogue":
            fail(f"{component}: businessScope mismatch")
    return ready


def validate_flows(contract: dict[str, Any]) -> None:
    values = contract.get("approvedFlows")
    if not isinstance(values, list):
        fail("approvedFlows must be a list")
    actual: set[tuple[str, str, str]] = set()
    for value in values:
        if not isinstance(value, dict):
            fail("each flow must be an object")
        edge = (value.get("from"), value.get("to"), value.get("signal"))
        if edge in actual:
            fail(f"duplicate flow: {edge}")
        actual.add(edge)
        if value.get("mutating") is not False:
            fail(f"flow may not grant mutation authority: {edge}")
        if not isinstance(value.get("ownership"), str) or not value["ownership"]:
            fail(f"flow requires an ownership statement: {edge}")
    if actual != EXPECTED_FLOWS:
        fail(f"flow mismatch; missing={sorted(EXPECTED_FLOWS-actual)}, unexpected={sorted(actual-EXPECTED_FLOWS)}")


def validate_boundaries(contract: dict[str, Any]) -> None:
    expected_isolation = {
        "tenantKey": "codestra_business",
        "deploymentControlledIdentity": True,
        "callerControlledBusinessAllowed": False,
        "crossBusinessDefaultAllowed": False,
        "grafanaBusinessAccessEnabled": False,
        "supersetBusinessAccessEnabled": False,
        "openBaoCrossBusinessWildcardAllowed": False,
    }
    if contract.get("businessIsolation") != expected_isolation:
        fail("businessIsolation mismatch")

    expected_security = {
        "nativePublicPortsAllowed": False,
        "immutableDigestRequired": True,
        "secretMaterialInGitAllowed": False,
        "runtimeCredentialsFromOpenBaoOrSecretFiles": True,
        "mtlsAndCaVerificationRequiredWhereSpecified": True,
        "anonymousAccessAllowed": False,
        "insecureTlsVerificationAllowed": False,
        "telemetryDataMinimizationRequired": True,
        "businessMutationAuthorityAllowed": False,
        "communicationsDeliveryAuthorityAllowed": False,
        "financialTradingMutationAuthorityAllowed": False,
    }
    if contract.get("securityInvariants") != expected_security:
        fail("securityInvariants mismatch")

    beyvra = contract.get("beyvraBoundary")
    required_true = {
        "safeAggregateHealthVisible", "latencyVisible", "marketDataFreshnessVisible",
        "reconciliationStateVisible", "dependencyHealthVisible",
    }
    required_false = {
        "brokerExchangeCustodySecretsVisible", "tradeSigningAllowed",
        "tradeAuthorizationAllowed", "protectedPayloadDecryptionAllowed",
        "authoritativeLedgerMutationAllowed",
    }
    if not isinstance(beyvra, dict) or set(beyvra) != required_true | required_false:
        fail("Beyvra boundary field set mismatch")
    if any(beyvra[key] is not True for key in required_true):
        fail("Beyvra safe aggregate visibility is incomplete")
    if any(beyvra[key] is not False for key in required_false):
        fail("Beyvra mutation or credential authority is enabled")

    activation = contract.get("runtimeActivation")
    if not isinstance(activation, dict) or not activation:
        fail("runtimeActivation is required")
    if any(value is not False for value in activation.values()):
        fail("every runtime activation field must remain false")


def validate_milestone(contract: dict[str, Any], ready: bool) -> None:
    milestone = contract.get("milestone")
    if not isinstance(milestone, dict):
        fail("milestone must be an object")
    if milestone.get("name") != MILESTONE:
        fail("milestone name mismatch")
    if milestone.get("prohibitedClaims") != PROHIBITED:
        fail("prohibitedClaims mismatch")
    if milestone.get("achieved") is not ready:
        fail("milestone achieved state does not match computed readiness")
    expected = "SOURCE_READY_FOR_STAGING_PREPARATION" if ready else "SOURCE_COMPATIBILITY_REVIEW_PENDING"
    if milestone.get("status") != expected:
        fail(f"milestone status must be {expected}")


def validate_docs() -> None:
    if not DOC.is_file() or DOC.is_symlink():
        fail("V2 compatibility documentation is missing")
    text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "fourteen authorities",
        "Alertmanager",
        "PostgreSQL Exporter",
        "No component may absorb another component's authority",
        "No deployment is authorized",
        "Middleware-only",
        "database-native row-level security",
        "broker, exchange, or custody signing material",
    ):
        if phrase not in text:
            fail(f"V2 compatibility documentation is missing: {phrase}")


def main() -> int:
    if not CONTRACT.is_file() or CONTRACT.is_symlink():
        fail("V2 suite contract is missing")
    contract = load(CONTRACT)
    if contract.get("schemaVersion") != "2.0":
        fail("schemaVersion must be 2.0")
    if contract.get("suite") != "codestra-corporate-observability-analytics-security":
        fail("suite name mismatch")
    if contract.get("authorityCount") != 14:
        fail("authorityCount must be 14")
    if contract.get("businesses") != BUSINESSES:
        fail("business catalogue mismatch")
    if contract.get("canonicalDimensions") != DIMENSIONS:
        fail("canonicalDimensions mismatch")
    if contract.get("forbiddenIndexedDimensions") != FORBIDDEN_INDEXED:
        fail("forbiddenIndexedDimensions mismatch")

    ready = validate_authorities(contract)
    validate_flows(contract)
    validate_boundaries(contract)
    validate_milestone(contract, ready)
    validate_docs()

    serialized = json.dumps(contract, sort_keys=True)
    dash = chr(45) * 5
    for signature in (
        dash + "BEGIN " + "OPENSSH" + " PRIVATE" + " KEY" + dash,
        "A" + "K" + "I" + "A",
    ):
        if signature in serialized:
            fail("secret-shaped material is forbidden")

    print("CODESTRA_SUITE_AUTHORITY_COUNT=14")
    print(f"CODESTRA_SUITE_SOURCE_READY={'YES' if ready else 'NO'}")
    print("CODESTRA_SUITE_DEPLOYMENT_AUTHORIZED=NO")
    print("CODESTRA_SUITE_V2_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"CODESTRA_SUITE_V2_ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
