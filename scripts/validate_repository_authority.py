#!/usr/bin/env python3
"""Validate the complete non-activating Telemetry repository authority."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
BRANCHES = ["development", "test", "staging", "production", "main"]
REQUIRED = (
    "README.md",
    "REPOSITORY_PROFILE.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    ".gitleaks.toml",
    "docs/BACKUP_RESTORE_ROLLBACK.md",
    "docs/UPGRADE.md",
    "upstream/LICENSE",
    "codestra/compose.candidate.yaml",
    "codestra/control-api/compose.candidate.yaml",
    "codestra/release/image-build.v1.json",
    "codestra/control-api/release/image-build.v1.json",
)
UPSTREAM_TEST_KEY_ALLOWLIST = {
    r"^upstream/config/configgrpc/testdata/client\.key$",
    r"^upstream/config/configgrpc/testdata/server\.key$",
    r"^upstream/config/confighttp/testdata/client\.key$",
    r"^upstream/config/confighttp/testdata/server\.key$",
    r"^upstream/config/configtls/testdata/client-1\.key$",
    r"^upstream/config/configtls/testdata/client-2\.key$",
    r"^upstream/config/configtls/testdata/server-1\.key$",
    r"^upstream/config/configtls/testdata/server-2\.key$",
    r"^upstream/exporter/otlpexporter/testdata/test_key\.pem$",
}


def fail(message: str) -> None:
    raise SystemExit(f"TELEMETRY_REPOSITORY_AUTHORITY=FAIL reason={message}")


def load(relative: str) -> dict:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{relative} must be an object")
    return value


def main() -> None:
    missing = [relative for relative in REQUIRED if not (ROOT / relative).is_file()]
    if missing:
        fail(f"missing files: {missing}")

    authority = load("CODESTRA_UPSTREAM.json")
    lock = load("CODESTRA_UPSTREAM_LOCK.json")
    if authority.get("schema_version") != "1.1" or lock.get("schema_version") != "1.1":
        fail("upstream authority schema must be 1.1")
    if authority.get("codestra_repository") != "appolon1908-hue/Codestra-Telemetry":
        fail("repository identity mismatch")
    if authority.get("branches") != BRANCHES:
        fail("promotion branch model mismatch")
    if authority.get("deployment_enabled") is not False or lock.get("deployment_enabled") is not False:
        fail("source authority may not activate deployment")
    for key in ("upstream_commit", "imported_tree_sha"):
        if not SHA.fullmatch(str(lock.get(key, ""))):
            fail(f"invalid upstream lock field: {key}")
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD:upstream"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tree != lock["imported_tree_sha"]:
        fail("vendored upstream tree differs from its lock")

    gitleaks = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
    allowlisted_paths = set(re.findall(r"(?m)^\s*'''([^']+)''',?\s*$", gitleaks))
    if gitleaks.count("[[allowlists]]") != 1 or allowlisted_paths != UPSTREAM_TEST_KEY_ALLOWLIST:
        fail("gitleaks exception set must contain only the locked upstream test keys")

    for relative in (
        "codestra/release/image-build.v1.json",
        "codestra/control-api/release/image-build.v1.json",
    ):
        manifest = load(relative)
        if manifest.get("productionActivation") is not False:
            fail(f"image manifest activates production: {relative}")
        args = manifest.get("buildArgs")
        if not isinstance(args, dict) or not args or any(
            not IMAGE.fullmatch(str(value)) for value in args.values()
        ):
            fail(f"mutable build authority: {relative}")

    profile = (ROOT / "REPOSITORY_PROFILE.md").read_text(encoding="utf-8")
    for text in (
        "REPO_RELEASE_READY=BLOCKED",
        "internal_private",
        "development -> test -> staging -> production -> main",
        "hotfix/*",
        "Native OTLP, health, diagnostics, metrics, and control API ports remain private",
        "productionActivation=false",
        "does not start a workload",
    ):
        if text not in profile:
            fail(f"repository profile omits: {text}")

    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        source = workflow.read_text(encoding="utf-8")
        for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", source):
            if not reference.startswith("./") and not re.fullmatch(
                r"[^@\s]+@[0-9a-f]{40}", reference
            ):
                fail(f"mutable action reference in {workflow.name}: {reference}")
        if re.search(
            r"git push\s+origin\s+HEAD:(?:development|test|staging|production|main)",
            source,
        ):
            fail(f"direct protected-branch push in {workflow.name}")

    print("TELEMETRY_REPOSITORY_AUTHORITY=PASS")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
