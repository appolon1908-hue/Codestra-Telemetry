#!/usr/bin/env python3
"""Verify the source snapshot against GitHub without exposing credentials."""
from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from validate_repository_development_lock import (
    AUTHORITY_SHA,
    EXPECTED,
    INVENTORY_PATH,
    LOCK_PATH,
    load,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_TELEMETRY_LOCK_CHANGES = {
    ".github/workflows/validate-repository-development-lock.yml",
    "REPOSITORY_DEVELOPMENT_LOCK.json",
    "deploy/evidence/CODESTRA-OBSERVABILITY-SOURCE-INVENTORY.json",
    "scripts/validate_repository_development_lock.py",
    "scripts/verify_repository_development_lock_remote.py",
    "tests/test_repository_development_lock.py",
}


def fail(message: str) -> None:
    raise SystemExit(f"REPOSITORY_DEVELOPMENT_REMOTE=FAIL reason={message}")


def command(args: list[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 and not allow_failure:
        fail(f"command failed without credential output: {args[0]} {args[1]}")
    return result


def gh_json(args: list[str]) -> Any:
    result = command(["gh", *args])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"GitHub returned invalid JSON for {args[0]}")
        raise AssertionError from exc


def api(path: str) -> Any:
    return gh_json(["api", path])


def repository_content(repository: str, path: str, revision: str) -> str:
    result = api(f"repos/{repository}/contents/{path}?ref={revision}")
    if result.get("encoding") != "base64" or not isinstance(result.get("content"), str):
        fail(f"invalid GitHub content response: {repository}/{path}")
    return base64.b64decode(result["content"]).decode("utf-8")


def verify_telemetry_lock_commit(locked_sha: str, remote_sha: str) -> None:
    head = command(["git", "rev-parse", "HEAD"]).stdout.strip()
    if remote_sha not in {locked_sha, head}:
        fail("Telemetry development moved outside the reviewed lock change")
    if head == locked_sha:
        return
    if command(["git", "merge-base", "--is-ancestor", locked_sha, head], allow_failure=True).returncode != 0:
        fail("Telemetry lock source is not an ancestor of the exact validation head")
    changed = set(
        filter(
            None,
            command(["git", "diff", "--name-only", f"{locked_sha}..{head}"]).stdout.splitlines(),
        )
    )
    if not changed or not changed <= ALLOWED_TELEMETRY_LOCK_CHANGES:
        fail(f"Telemetry changed outside the source-lock boundary: {sorted(changed)}")


def main() -> None:
    lock = load(LOCK_PATH)
    inventory = load(INVENTORY_PATH)
    try:
        validate(lock, inventory)
    except ValueError as exc:
        fail(str(exc))
    lock_by_repo = {item["repository"]: item for item in lock["repositories"]}
    inventory_by_repo = {item["repository"]: item for item in inventory["repositories"]}

    for repository, pull_number in EXPECTED.values():
        locked = lock_by_repo[repository]
        observed = inventory_by_repo[repository]
        revision = locked["developmentSha"]

        branch_result = command(
            ["gh", "api", f"repos/{repository}/branches/development"],
            allow_failure=True,
        )
        if locked["developmentRefState"] == "PRESENT":
            if branch_result.returncode != 0:
                fail(f"development ref is unexpectedly absent: {repository}")
            remote_sha = json.loads(branch_result.stdout)["commit"]["sha"]
            if repository == "appolon1908-hue/Codestra-Telemetry":
                verify_telemetry_lock_commit(revision, remote_sha)
            elif remote_sha != revision:
                fail(f"development SHA moved after lock capture: {repository}")
        else:
            if branch_result.returncode == 0:
                fail(f"deleted development ref unexpectedly exists: {repository}")
            evidence_pr = api(
                f"repos/{repository}/pulls/{locked['developmentHeadEvidencePullRequest']}"
            )
            if (
                evidence_pr.get("merged") is not True
                or evidence_pr.get("head", {}).get("sha") != revision
                or evidence_pr.get("head", {}).get("ref") != "development"
            ):
                fail(f"deleted development ref evidence mismatch: {repository}")

        runs = api(f"repos/{repository}/actions/runs?head_sha={revision}&per_page=100")[
            "workflow_runs"
        ]
        push_runs = [run for run in runs if run.get("event") == "push"]
        if len([run for run in push_runs if run.get("conclusion") == "success"]) < locked[
            "successfulProtectedPushRuns"
        ]:
            fail(f"successful protected run count regressed: {repository}")
        if any(run.get("status") != "completed" or run.get("conclusion") != "success" for run in push_runs):
            fail(f"non-successful exact protected push run: {repository}")

        source_pr = api(f"repos/{repository}/pulls/{pull_number}")
        if (
            source_pr.get("state", "").upper() != observed["state"]
            or source_pr.get("merged") is not observed["merged"]
            or source_pr.get("draft") is not observed["isDraft"]
            or source_pr.get("head", {}).get("ref") != observed["headBranch"]
            or source_pr.get("head", {}).get("sha") != observed["headSha"]
            or source_pr.get("base", {}).get("ref") != observed["baseBranch"]
        ):
            fail(f"source pull request snapshot drift: {repository}#{pull_number}")
        if observed["merged"] and source_pr.get("merge_commit_sha") != observed["mergeSha"]:
            fail(f"source pull request merge SHA drift: {repository}#{pull_number}")
        files = api(f"repos/{repository}/pulls/{pull_number}/files?per_page=100")
        if sorted(item["filename"] for item in files) != sorted(observed["changedFilenames"]):
            fail(f"source pull request file set drift: {repository}#{pull_number}")

        check_data = gh_json(
            [
                "pr",
                "view",
                str(pull_number),
                "--repo",
                repository,
                "--json",
                "statusCheckRollup",
            ]
        )
        check_states: dict[str, set[str]] = {}
        for check in check_data.get("statusCheckRollup", []):
            name = check.get("name") or check.get("context")
            conclusion = check.get("conclusion") or check.get("state")
            if name:
                check_states.setdefault(name, set()).add(str(conclusion))
        if set(check_states) != set(observed["requiredCheckNames"]):
            fail(f"source pull request check set drift: {repository}#{pull_number}")
        if any(states != {"SUCCESS"} for states in check_states.values()):
            fail(f"source pull request has a non-successful check: {repository}#{pull_number}")

        query = (
            "query { repository(owner:\"appolon1908-hue\", "
            f"name:\"{repository.split('/', 1)[1]}\") {{ pullRequest(number:{pull_number}) "
            "{ reviewThreads(first:100) { nodes { isResolved } } } } }"
        )
        thread_data = gh_json(["api", "graphql", "-f", f"query={query}"])
        threads = thread_data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        if len([thread for thread in threads if not thread["isResolved"]]) != observed[
            "unresolvedReviewThreadCount"
        ]:
            fail(f"review-thread snapshot drift: {repository}#{pull_number}")

        if repository == "appolon1908-hue/Codestra-Telemetry":
            repository_content(repository, "codestra/api/service-contract.schema.json", AUTHORITY_SHA)
            repository_content(
                repository,
                ".github/workflows/reusable-validate-service-contract.yml",
                AUTHORITY_SHA,
            )
        else:
            contract = json.loads(
                repository_content(
                    repository, "codestra/api/service-contract.v1.json", revision
                )
            )
            if contract.get("schemaAuthority", {}).get("sourceRevision") != AUTHORITY_SHA:
                fail(f"downstream schema authority drift: {repository}")
            workflow = repository_content(
                repository,
                ".github/workflows/validate-codestra-service-contract.yml",
                revision,
            )
            reference = re.findall(
                r"reusable-validate-service-contract\.yml@([0-9a-f]{40})", workflow
            )
            if set(reference) != {AUTHORITY_SHA}:
                fail(f"downstream reusable workflow authority drift: {repository}")
            if repository.endswith("Codestra-Postgres-Exporter") and (
                contract.get("nativeExposure") != "internal_private"
                or contract.get("canonicalHostname") != "postgres-exporter"
            ):
                fail("PostgreSQL Exporter superseding contract is not private-only")

    obsolete = api("repos/appolon1908-hue/Codestra-OpenBao/pulls/30")
    if obsolete.get("state") != "closed" or obsolete.get("merged") is not False:
        fail("OpenBao PR 30 is not closed and unmerged")

    print("REPOSITORY_DEVELOPMENT_REMOTE=PASS")
    print("REMOTE_REPOSITORIES_VERIFIED=14/14")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
