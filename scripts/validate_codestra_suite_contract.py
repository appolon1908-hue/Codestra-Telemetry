#!/usr/bin/env python3
"""Validate the Codestra twelve-product corporate suite source contract."""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "codestra" / "suite-contract.v1.json"
DOC_PATH = ROOT / "codestra" / "docs" / "SUITE-COMPATIBILITY-GATE.md"

BUSINESSES = [
    "codestra",
    "moneybee",
    "beyvra",
    "breero",
    "larim-a",
    "transportation",
    "booked4seasons",
    "social",
    "klyrow",
    "telnexa",
    "kyqra",
    "restaurant",
    "provisioning",
]

DIMENSIONS = [
    "codestra_business",
    "application",
    "service",
    "environment",
    "server",
    "region",
    "deployment",
]

FORBIDDEN_INDEXED_DIMENSIONS = {
    "tenant_id",
    "customer_id",
    "user_id",
    "email",
    "phone",
    "request_id",
    "trace_id",
    "message_id",
    "order_id",
    "payment_id",
    "transaction_id",
    "db_statement",
    "raw_url",
    "container_id",
    "pod_uid",
}

AUTHORITIES = {
    "loki": (
        1,
        "appolon1908-hue/Codestra-Loki",
        "loki.codestra.media",
        "central-log-authority",
        "internal_private",
    ),
    "prometheus": (
        2,
        "appolon1908-hue/Codestra-Prometheus",
        "prom.codestra.media",
        "metrics-slo-alert-evaluation-authority",
        "internal_private",
    ),
    "grafana": (
        3,
        "appolon1908-hue/Codestra-Grafana-",
        "graf.codestra.media",
        "read-only-operational-presentation-authority",
        "loopback_edge_only",
    ),
    "tempo": (
        4,
        "appolon1908-hue/Codestra-Tempo",
        "temp.codestra.media",
        "distributed-trace-authority",
        "internal_private",
    ),
    "opentelemetry": (
        5,
        "appolon1908-hue/Codestra-Telemetry",
        "otel.codestra.media",
        "telemetry-ingress-normalization-redaction-routing-authority",
        "internal_private",
    ),
    "alloy": (
        6,
        "appolon1908-hue/Codestra-Alloy",
        "allo.codestra.media",
        "host-service-log-collection-agent-authority",
        "internal_private",
    ),
    "node-exporter": (
        7,
        "appolon1908-hue/Codestra-Node-Exporter",
        "node.codestra.media",
        "host-metrics-operational-evidence-authority",
        "internal_private",
    ),
    "cadvisor": (
        8,
        "appolon1908-hue/Codestra-cAdvisor",
        "cadv.codestra.media",
        "container-resource-metrics-authority",
        "internal_private",
    ),
    "redis-exporter": (
        9,
        "appolon1908-hue/Codestra-Redis-Exporter",
        "rdex.codestra.media",
        "redis-health-capacity-persistence-metrics-authority",
        "internal_private",
    ),
    "blackbox-exporter": (
        10,
        "appolon1908-hue/Codestra-Blackbox-Exporter",
        "blac.codestra.media",
        "synthetic-availability-dns-tls-authority",
        "internal_private",
    ),
    "superset": (
        11,
        "appolon1908-hue/Superset",
        "supe.codestra.media",
        "certified-read-only-business-analytics-authority",
        "loopback_edge_only",
    ),
    "openbao": (
        12,
        "appolon1908-hue/Codestra-OpenBao",
        "bao.codestra.media",
        "secrets-pki-workload-identity-authority",
        "private_strong_auth",
    ),
}

EXPECTED_FLOWS = {
    ("alloy", "loki", "logs"),
    ("opentelemetry", "loki", "logs"),
    ("opentelemetry", "prometheus", "metrics"),
    ("opentelemetry", "tempo", "traces"),
    ("node-exporter", "prometheus", "metrics"),
    ("cadvisor", "prometheus", "metrics"),
    ("redis-exporter", "prometheus", "metrics"),
    ("blackbox-exporter", "prometheus", "metrics"),
    ("prometheus", "grafana", "metrics"),
    ("loki", "grafana", "logs"),
    ("tempo", "grafana", "traces"),
    ("certified-readonly-datasets", "superset", "analytics"),
    ("openbao", "suite-workloads", "identity-certificates-secrets"),
}

MILESTONE = "CODESTRA_CORPORATE_SUITE_SOURCE_READY_FOR_STAGING_REVIEW"
PROHIBITED_CLAIMS = ["DEPLOYED", "PRODUCTION_READY", "RUNTIME_ACTIVATED"]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    print(f"CODESTRA_SUITE_CONTRACT_ERROR={message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.relative_to(ROOT)} must contain an object")
    return value


def require_exact_list(value: Any, expected: list[str], label: str) -> None:
    if value != expected:
        fail(f"{label} must exactly match the canonical ordered list")
    if len(value) != len(set(value)):
        fail(f"{label} contains duplicates")


def validate_authorities(contract: dict[str, Any]) -> bool:
    values = contract.get("authorities")
    if not isinstance(values, list) or len(values) != len(AUTHORITIES):
        fail("exactly twelve authority records are required")

    by_component: dict[str, dict[str, Any]] = {}
    repositories: set[str] = set()
    hostnames: set[str] = set()
    source_heads: set[tuple[str, str]] = set()
    all_ready = True

    for item in values:
        if not isinstance(item, dict):
            fail("each authority record must be an object")
        component = item.get("component")
        if component in by_component:
            fail(f"duplicate component authority: {component}")
        if component not in AUTHORITIES:
            fail(f"unapproved component authority: {component}")
        by_component[component] = item

        sequence, repository, hostname, role, exposure = AUTHORITIES[component]
        expected = {
            "sequence": sequence,
            "repository": repository,
            "canonicalHostname": hostname,
            "role": role,
            "nativeExposure": exposure,
        }
        for key, expected_value in expected.items():
            if item.get(key) != expected_value:
                fail(f"{component}: {key} must be {expected_value!r}")

        if repository in repositories:
            fail(f"repository owns more than one authority: {repository}")
        repositories.add(repository)
        if hostname in hostnames:
            fail(f"canonical hostname is duplicated: {hostname}")
        hostnames.add(hostname)

        source_pr = item.get("sourcePr")
        if not isinstance(source_pr, int) or source_pr < 1:
            fail(f"{component}: sourcePr must be a positive integer")
        source_head = item.get("sourceHead")
        if not isinstance(source_head, str) or not SHA_RE.fullmatch(source_head):
            fail(f"{component}: sourceHead must be a full lowercase Git SHA")
        if (repository, source_head) in source_heads:
            fail(f"duplicate repository/source-head evidence: {repository}@{source_head}")
        source_heads.add((repository, source_head))

        source_state = item.get("sourceState")
        if source_state not in {"promoted-development", "review-open"}:
            fail(f"{component}: invalid sourceState")
        exact_checks = item.get("exactHeadChecks")
        if exact_checks not in {"success", "pending", "failure"}:
            fail(f"{component}: invalid exactHeadChecks state")
        if exact_checks != "success":
            all_ready = False

        review = item.get("reviewEvidence")
        if not isinstance(review, dict):
            fail(f"{component}: reviewEvidence must be an object")
        review_state = review.get("state")
        unresolved = review.get("unresolvedThreads")
        if review_state == "complete":
            if not isinstance(unresolved, int) or unresolved < 0:
                fail(f"{component}: complete review evidence requires a non-negative unresolved count")
            if unresolved != 0:
                all_ready = False
        elif review_state == "pending":
            if unresolved is not None:
                fail(f"{component}: pending review evidence must use null unresolvedThreads")
            all_ready = False
        else:
            fail(f"{component}: invalid reviewEvidence state")

        if item.get("sourceOnlyStatus") != "CONFIG_PREPARED_NOT_DEPLOYED":
            fail(f"{component}: source-only status changed")
        if item.get("activationClaim") is not False:
            fail(f"{component}: activationClaim must remain false")
        if item.get("businessScope") != "canonical-suite-catalogue":
            fail(f"{component}: businessScope must reference the canonical suite catalogue")

    if set(by_component) != set(AUTHORITIES):
        fail("authority component set is incomplete")
    if [item["sequence"] for item in values] != list(range(1, 13)):
        fail("authorities must be ordered 1 through 12")
    return all_ready


def validate_flows(contract: dict[str, Any]) -> None:
    flows = contract.get("approvedFlows")
    if not isinstance(flows, list):
        fail("approvedFlows must be a list")
    actual: set[tuple[str, str, str]] = set()
    for flow in flows:
        if not isinstance(flow, dict):
            fail("each approved flow must be an object")
        edge = (flow.get("from"), flow.get("to"), flow.get("signal"))
        if not all(isinstance(value, str) and value for value in edge):
            fail("approved flow endpoints and signal must be non-empty strings")
        if edge in actual:
            fail(f"duplicate approved flow: {edge}")
        actual.add(edge)
        if flow.get("mutating") is not False:
            fail(f"suite data flow may not grant mutation authority: {edge}")
        if not isinstance(flow.get("ownership"), str) or not flow["ownership"]:
            fail(f"approved flow requires an ownership statement: {edge}")
    if actual != EXPECTED_FLOWS:
        missing = sorted(EXPECTED_FLOWS - actual)
        unexpected = sorted(actual - EXPECTED_FLOWS)
        fail(f"approved flow mismatch; missing={missing}, unexpected={unexpected}")


def validate_boundaries(contract: dict[str, Any]) -> None:
    isolation = contract.get("businessIsolation")
    expected_isolation = {
        "tenantKey": "codestra_business",
        "deploymentControlledIdentity": True,
        "callerControlledBusinessAllowed": False,
        "crossBusinessDefaultAllowed": False,
        "grafanaBusinessAccessEnabled": False,
        "supersetBusinessAccessEnabled": False,
        "openBaoCrossBusinessWildcardAllowed": False,
    }
    if isolation != expected_isolation:
        fail("businessIsolation contract mismatch")

    security = contract.get("securityInvariants")
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
    if security != expected_security:
        fail("securityInvariants contract mismatch")

    beyvra = contract.get("beyvraBoundary")
    if not isinstance(beyvra, dict):
        fail("beyvraBoundary must be an object")
    required_true = {
        "safeAggregateHealthVisible",
        "latencyVisible",
        "marketDataFreshnessVisible",
        "reconciliationStateVisible",
        "dependencyHealthVisible",
    }
    required_false = {
        "brokerExchangeCustodySecretsVisible",
        "tradeSigningAllowed",
        "tradeAuthorizationAllowed",
        "protectedPayloadDecryptionAllowed",
        "authoritativeLedgerMutationAllowed",
    }
    for key in required_true:
        if beyvra.get(key) is not True:
            fail(f"Beyvra safe visibility must be true: {key}")
    for key in required_false:
        if beyvra.get(key) is not False:
            fail(f"Beyvra authority must be false: {key}")
    if set(beyvra) != required_true | required_false:
        fail("unexpected Beyvra boundary field")

    activation = contract.get("runtimeActivation")
    if not isinstance(activation, dict) or not activation:
        fail("runtimeActivation must be a non-empty object")
    enabled = sorted(key for key, value in activation.items() if value is not False)
    if enabled:
        fail(f"all runtime activation fields must remain false: {enabled}")


def validate_milestone(contract: dict[str, Any], computed_ready: bool) -> None:
    milestone = contract.get("milestone")
    if not isinstance(milestone, dict):
        fail("milestone must be an object")
    if milestone.get("name") != MILESTONE:
        fail("milestone name mismatch")
    if milestone.get("prohibitedClaims") != PROHIBITED_CLAIMS:
        fail("prohibited milestone claims mismatch")
    achieved = milestone.get("achieved")
    if not isinstance(achieved, bool):
        fail("milestone achieved must be boolean")
    if achieved != computed_ready:
        fail(f"milestone achieved={achieved} does not match computed readiness={computed_ready}")
    expected_status = (
        "SOURCE_READY_FOR_STAGING_REVIEW"
        if computed_ready
        else "SOURCE_COMPATIBILITY_REVIEW_PENDING"
    )
    if milestone.get("status") != expected_status:
        fail(f"milestone status must be {expected_status}")


def validate_documentation() -> None:
    try:
        text = DOC_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read {DOC_PATH.relative_to(ROOT)}: {exc}")
    for required in (
        MILESTONE,
        "No component may absorb another component's authority",
        "folder permissions alone are insufficient",
        "database-native RLS",
        "broker/exchange/custody signing material",
        "This gate creates files, validation, and review evidence only",
    ):
        if required not in text:
            fail(f"compatibility documentation is missing: {required}")
    for claim in PROHIBITED_CLAIMS:
        if f"```text\n{claim}\n```" in text:
            # The document must be allowed to list prohibited claims in one multi-line block.
            fail(f"documentation presents prohibited claim as a positive standalone milestone: {claim}")


def scan_for_credential_values(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if any(token in normalized for token in ("password", "clientsecret", "privatekey", "roottoken", "apikey")):
                if isinstance(child, str) and child.strip():
                    fail(f"credential-like string committed at {path}{key}")
            scan_for_credential_values(child, f"{path}{key}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_for_credential_values(child, f"{path}{index}.")


def main() -> None:
    contract = load_json(CONTRACT_PATH)
    if contract.get("schemaVersion") != "1.0":
        fail("schemaVersion must be 1.0")
    if contract.get("suite") != "codestra-corporate-observability-analytics-security":
        fail("suite identifier mismatch")

    require_exact_list(contract.get("businesses"), BUSINESSES, "businesses")
    require_exact_list(contract.get("canonicalDimensions"), DIMENSIONS, "canonicalDimensions")

    forbidden = contract.get("forbiddenIndexedDimensions")
    if not isinstance(forbidden, list) or set(forbidden) != FORBIDDEN_INDEXED_DIMENSIONS:
        fail("forbiddenIndexedDimensions must match the approved privacy/cardinality set")
    if len(forbidden) != len(set(forbidden)):
        fail("forbiddenIndexedDimensions contains duplicates")

    authorities_ready = validate_authorities(contract)
    validate_flows(contract)
    validate_boundaries(contract)
    validate_milestone(contract, authorities_ready)
    validate_documentation()
    scan_for_credential_values(contract)

    if authorities_ready:
        print(f"{MILESTONE}=1")
    else:
        print("CODESTRA_CORPORATE_SUITE_SOURCE_COMPATIBILITY_REVIEW_PENDING=1")
    print("CODESTRA_SUITE_CONTRACT_VALIDATION_PASS=1")


if __name__ == "__main__":
    main()
