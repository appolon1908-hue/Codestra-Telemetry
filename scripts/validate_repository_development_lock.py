#!/usr/bin/env python3
"""Fail-closed structural validation for the fourteen-repository source lock."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "REPOSITORY_DEVELOPMENT_LOCK.json"
INVENTORY_PATH = (
    ROOT / "deploy/evidence/CODESTRA-OBSERVABILITY-SOURCE-INVENTORY.json"
)
SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")
AUTHORITY_SHA = "c35d880a730ca5206d445e8a9a688cb465ae2ad4"
EXPECTED = {
    "opentelemetry": ("appolon1908-hue/Codestra-Telemetry", 17),
    "prometheus": ("appolon1908-hue/Codestra-Prometheus", 29),
    "grafana": ("appolon1908-hue/Codestra-Grafana-", 17),
    "alertmanager": ("appolon1908-hue/Codestra-Alertmanager", 6),
    "loki": ("appolon1908-hue/Codestra-Loki", 17),
    "tempo": ("appolon1908-hue/Codestra-Tempo", 15),
    "alloy": ("appolon1908-hue/Codestra-Alloy", 17),
    "node-exporter": ("appolon1908-hue/Codestra-Node-Exporter", 21),
    "cadvisor": ("appolon1908-hue/Codestra-cAdvisor", 18),
    "redis-exporter": ("appolon1908-hue/Codestra-Redis-Exporter", 18),
    "postgres-exporter": ("appolon1908-hue/Codestra-Postgres-Exporter", 6),
    "blackbox-exporter": ("appolon1908-hue/Codestra-Blackbox-Exporter", 18),
    "superset": ("appolon1908-hue/Superset", 17),
    "openbao": ("appolon1908-hue/Codestra-OpenBao", 33),
}


def fail(message: str) -> None:
    raise ValueError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        fail(f"{path.name} must contain an object")
    return value


def validate(lock: dict[str, Any], inventory: dict[str, Any]) -> None:
    if lock.get("schemaVersion") != "1.0.0" or inventory.get("schemaVersion") != "1.0.0":
        fail("unsupported repository lock or inventory schema")
    if lock.get("productionActivation") is not False or inventory.get("productionActivation") is not False:
        fail("source evidence may not activate production")
    authority = lock.get("canonicalSchema", {})
    if authority != {
        "repository": "appolon1908-hue/Codestra-Telemetry",
        "version": "1.0.0",
        "sourceRevision": AUTHORITY_SHA,
        "path": "codestra/api/service-contract.schema.json",
        "reusableWorkflowRevision": AUTHORITY_SHA,
        "reusableWorkflowPath": ".github/workflows/reusable-validate-service-contract.yml",
    }:
        fail("canonical schema or reusable workflow authority mismatch")
    if inventory.get("repositoryCount") != 14:
        fail("source inventory repository count must be fourteen")
    for field in ("schemaAuthoritySha", "reusableWorkflowAuthoritySha"):
        if inventory.get(field) != AUTHORITY_SHA:
            fail(f"source inventory {field} mismatch")

    locked = lock.get("repositories")
    observed = inventory.get("repositories")
    if not isinstance(locked, list) or not isinstance(observed, list):
        fail("repository entries must be arrays")
    if len(locked) != 14 or len(observed) != 14:
        fail("repository lock and inventory must each contain fourteen entries")
    lock_by_id = {entry.get("serviceId"): entry for entry in locked}
    inventory_by_repo = {entry.get("repository"): entry for entry in observed}
    if set(lock_by_id) != set(EXPECTED) or len(lock_by_id) != len(locked):
        fail("repository lock component set is incomplete or duplicated")
    if set(inventory_by_repo) != {item[0] for item in EXPECTED.values()} or len(inventory_by_repo) != len(observed):
        fail("source inventory repository set is incomplete or duplicated")

    for service_id, (repository, pull_request) in EXPECTED.items():
        entry = lock_by_id[service_id]
        if entry.get("repository") != repository or entry.get("sourcePullRequest") != pull_request:
            fail(f"repository lock identity mismatch: {service_id}")
        if not SHA.fullmatch(str(entry.get("developmentSha", ""))):
            fail(f"invalid development SHA: {service_id}")
        if entry.get("developmentRefState") not in {"PRESENT", "DELETED_AFTER_PROMOTION"}:
            fail(f"invalid development ref state: {service_id}")
        if not isinstance(entry.get("successfulProtectedPushRuns"), int) or entry["successfulProtectedPushRuns"] < 1:
            fail(f"no successful exact protected push run: {service_id}")
        expected_outcome = (
            "SUPERSEDED_UNSAFE_PUBLIC_EXPOSURE"
            if service_id == "postgres-exporter"
            else "MERGED"
        )
        if entry.get("sourcePullRequestOutcome") != expected_outcome:
            fail(f"source pull request outcome mismatch: {service_id}")
        if service_id == "postgres-exporter" and entry.get("supersedingPullRequest") != 7:
            fail("PostgreSQL Exporter unsafe source PR must be superseded by PR 7")
        if service_id == "alertmanager" and (
            entry.get("developmentRefState") != "DELETED_AFTER_PROMOTION"
            or entry.get("developmentHeadEvidencePullRequest") != 9
        ):
            fail("Alertmanager deleted development ref evidence is incomplete")

        source = inventory_by_repo[repository]
        if source.get("pullRequest") != pull_request or source.get("state") != "CLOSED":
            fail(f"source pull request state mismatch: {repository}")
        expected_merged = service_id != "postgres-exporter"
        if source.get("merged") is not expected_merged:
            fail(f"source pull request merge outcome mismatch: {repository}")
        if source.get("baseBranch") != "development":
            fail(f"source pull request base mismatch: {repository}")
        for field in ("headSha",):
            if not SHA.fullmatch(str(source.get(field, ""))):
                fail(f"invalid {field}: {repository}")
        if expected_merged and not SHA.fullmatch(str(source.get("mergeSha", ""))):
            fail(f"invalid merge SHA: {repository}")
        if source.get("unresolvedReviewThreadCount") != 0:
            fail(f"unresolved review thread: {repository}")
        checks = source.get("requiredCheckNames")
        conclusions = source.get("checkConclusions")
        if not isinstance(checks, list) or not checks or len(checks) != len(set(checks)):
            fail(f"required check set is empty or duplicated: {repository}")
        if not isinstance(conclusions, dict) or set(conclusions) != set(checks):
            fail(f"check conclusion set mismatch: {repository}")
        if set(conclusions.values()) != {"SUCCESS"}:
            fail(f"non-successful exact-head check: {repository}")
        files = source.get("changedFilenames")
        if not isinstance(files, list) or not files or len(files) != len(set(files)):
            fail(f"changed filename set is empty or duplicated: {repository}")
        if any(
            not isinstance(path, str)
            or not SAFE_PATH.fullmatch(path)
            or path.startswith("/")
            or ".." in Path(path).parts
            for path in files
        ):
            fail(f"unsafe changed filename: {repository}")
        for field in ("schemaAuthoritySha", "reusableWorkflowAuthoritySha"):
            if source.get(field) != AUTHORITY_SHA:
                fail(f"{field} mismatch: {repository}")

    postgres = inventory_by_repo["appolon1908-hue/Codestra-Postgres-Exporter"]
    if (
        postgres.get("outcome") != "SUPERSEDED_UNSAFE_PUBLIC_EXPOSURE"
        or postgres.get("supersedingPullRequest") != 7
        or not SHA.fullmatch(str(postgres.get("supersedingHeadSha", "")))
        or not SHA.fullmatch(str(postgres.get("supersedingMergeSha", "")))
    ):
        fail("PostgreSQL Exporter supersession evidence mismatch")
    superseded = inventory.get("explicitlySupersededPullRequests")
    if superseded != [
        {
            "repository": "appolon1908-hue/Codestra-OpenBao",
            "pullRequest": 30,
            "state": "CLOSED",
            "merged": False,
            "isDraft": True,
            "headSha": "ab173cebb684fe0de7703e7c42bf5fd4e0cf85d8",
            "supersededByPullRequest": 33,
        }
    ]:
        fail("OpenBao PR 30 supersession evidence mismatch")


def main() -> None:
    try:
        validate(load(LOCK_PATH), load(INVENTORY_PATH))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"REPOSITORY_DEVELOPMENT_LOCK=FAIL reason={exc}") from exc
    print("REPOSITORY_DEVELOPMENT_LOCK=PASS")
    print("REPOSITORIES_LOCKED=14/14")
    print("SOURCE_PRS_MERGED=13/14")
    print("SOURCE_PRS_SUPERSEDED_FOR_SAFETY=1/14")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
