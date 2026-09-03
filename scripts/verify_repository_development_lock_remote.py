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
    "docs/REPOSITORY-DEVELOPMENT-LOCK.md",
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


def protected_push_runs(runs: list[dict[str, Any]], branch: str) -> list[dict[str, Any]]:
    """Return only push evidence produced on the expected protected branch."""

    return [
        run
        for run in runs
        if run.get("event") == "push" and run.get("head_branch") == branch
    ]


def merge_is_ancestor(comparison: dict[str, Any]) -> bool:
    """Accept only a comparison proving base is equal to or behind head."""

    return comparison.get("status") in {"ahead", "identical"}


def postgres_supersession_matches(
    pull: dict[str, Any], observed: dict[str, Any]
) -> bool:
    return (
        pull.get("state") == "closed"
        and pull.get("merged") is True
        and pull.get("draft") is False
        and pull.get("number") == observed.get("supersedingPullRequest")
        and pull.get("head", {}).get("sha") == observed.get("supersedingHeadSha")
        and pull.get("base", {}).get("ref") == "development"
        and pull.get("merge_commit_sha") == observed.get("supersedingMergeSha")
    )


def commit_is_ancestor(base: str, head: str) -> bool:
    """Return whether ``base`` is an ancestor of ``head`` in the exact checkout."""

    return (
        command(
            ["git", "merge-base", "--is-ancestor", base, head],
            allow_failure=True,
        ).returncode
        == 0
    )


def changed_paths(base: str, head: str) -> set[str]:
    """Return the exact changed path set between two known commits."""

    if base == head:
        return set()
    return set(
        filter(
            None,
            command(["git", "diff", "--name-only", f"{base}..{head}"])
            .stdout.splitlines(),
        )
    )


def require_lock_only_transition(base: str, head: str, label: str) -> None:
    """Require an ancestry-preserving transition limited to lock-governance files."""

    if not commit_is_ancestor(base, head):
        fail(f"Telemetry {label} is not an ancestry-preserving transition")
    changed = changed_paths(base, head)
    if not changed <= ALLOWED_TELEMETRY_LOCK_CHANGES:
        fail(f"Telemetry changed outside the source-lock boundary: {sorted(changed)}")


def verify_telemetry_lock_commit(locked_sha: str, remote_sha: str) -> None:
    """Validate lock refreshes and protected promotion merge commits fail closed.

    ``locked_sha`` is the source snapshot recorded inside the lock. ``remote_sha``
    is the current protected development head. The local ``HEAD`` can be either a
    lock-refresh branch, the protected development head, or a merge commit on a
    later promotion branch. Every transition must preserve ancestry and may
    change only the established lock-governance file allowlist. A normal branch
    promotion can therefore use an empty tree diff without weakening the lock.
    """

    head = command(["git", "rev-parse", "HEAD"]).stdout.strip()
    require_lock_only_transition(locked_sha, remote_sha, "locked-to-development transition")
    require_lock_only_transition(remote_sha, head, "development-to-validation transition")


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

        protected_branch = "development"
        runs = api(
            f"repos/{repository}/actions/runs?branch={protected_branch}"
            f"&head_sha={revision}&per_page=100"
        )["workflow_runs"]
        push_runs = protected_push_runs(runs, protected_branch)
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
        if observed["merged"]:
            comparison = api(
                f"repos/{repository}/compare/{observed['mergeSha']}...{revision}"
            )
            if not merge_is_ancestor(comparison):
                fail(
                    "source pull request merge is not an ancestor of locked "
                    f"development: {repository}#{pull_number}"
                )
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

    postgres_observed = inventory_by_repo[
        "appolon1908-hue/Codestra-Postgres-Exporter"
    ]
    postgres_superseding = api(
        "repos/appolon1908-hue/Codestra-Postgres-Exporter/pulls/7"
    )
    if not postgres_supersession_matches(postgres_superseding, postgres_observed):
        fail("PostgreSQL Exporter superseding pull request evidence mismatch")
    postgres_compare = api(
        "repos/appolon1908-hue/Codestra-Postgres-Exporter/compare/"
        f"{postgres_observed['supersedingMergeSha']}..."
        f"{lock_by_repo['appolon1908-hue/Codestra-Postgres-Exporter']['developmentSha']}"
    )
    if not merge_is_ancestor(postgres_compare):
        fail("PostgreSQL Exporter superseding merge is not in locked development")

    obsolete = api("repos/appolon1908-hue/Codestra-OpenBao/pulls/30")
    if obsolete.get("state") != "closed" or obsolete.get("merged") is not False:
        fail("OpenBao PR 30 is not closed and unmerged")

    print("REPOSITORY_DEVELOPMENT_REMOTE=PASS")
    print("REMOTE_REPOSITORIES_VERIFIED=14/14")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
