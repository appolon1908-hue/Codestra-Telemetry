#!/usr/bin/env python3
"""Static fail-closed validation for the reusable Model B release authority."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reusable-release-config-bundle.yml"

REQUIRED = (
    "workflow_call:",
    "protected_source_sha:",
    "test \"$(git rev-parse origin/production)\" = \"$SOURCE_SHA\"",
    "persist-credentials: false",
    "packages: write",
    "id-token: write",
    "attestations: write",
    "trivy fs --exit-code 1 --severity HIGH,CRITICAL",
    "trivy image --exit-code 1 --severity HIGH,CRITICAL",
    "syft dir:dist/config-root",
    "cosign sign --yes",
    "cosign attest --yes --type spdxjson",
    "cosign verify-attestation",
    "push-to-registry: true",
    'gh attestation verify "oci://${IDENTITY}"',
    'oras pull "${registry}@${digest}"',
    'org.opencontainers.image.revision',
    "release tag already exists and may not be reassigned",
    "productionActivated:false",
)


def validate(source: str) -> None:
    for token in REQUIRED:
        if token not in source:
            raise ValueError(f"reusable release authority missing: {token}")
    if "latest" in source.lower():
        raise ValueError("reusable release authority contains a mutable latest reference")
    references = re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", source)
    for reference in references:
        if reference.startswith("./"):
            continue
        if not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference):
            raise ValueError(f"mutable action reference: {reference}")
    for value in re.findall(r"https://github\.com/[^\s\\]+/download/(v[0-9.]+)/", source):
        if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){1,2}", value):
            raise ValueError(f"mutable tool version: {value}")


def main() -> None:
    validate(WORKFLOW.read_text(encoding="utf-8"))
    print("REUSABLE_CONFIG_RELEASE_AUTHORITY=PASS")
    print("PRODUCTION_DEPLOYED=NO")


if __name__ == "__main__":
    main()
