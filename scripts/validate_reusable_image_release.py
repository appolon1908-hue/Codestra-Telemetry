#!/usr/bin/env python3
"""Static fail-closed validation for the reusable Model A image release."""
from __future__ import annotations
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/reusable-release-image.yml"
REQUIRED = (
    "workflow_call:", 'test "$GITHUB_REF" = "refs/heads/production"',
    'test "$(git rev-parse origin/production)" = "$SOURCE_SHA"',
    "release tag already exists and may not be reassigned", "--provenance=mode=max", "--sbom=true",
    "org.opencontainers.image.revision", "trivy image --exit-code 1 --severity HIGH,CRITICAL",
    "Build and scan a non-published exact candidate first", "org.opencontainers.image.created",
    "cosign sign --yes", "cosign verify-attestation", "push-to-registry: true",
    'gh attestation verify "oci://${IDENTITY}"', "productionActivated:false",
)
def validate(source: str) -> None:
    for token in REQUIRED:
        if token not in source: raise ValueError(f"reusable image release missing: {token}")
    for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", source):
        if not reference.startswith("./") and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference):
            raise ValueError(f"mutable action reference: {reference}")
def main() -> None:
    validate(WORKFLOW.read_text()); print("REUSABLE_IMAGE_RELEASE_AUTHORITY=PASS"); print("PRODUCTION_DEPLOYED=NO")
if __name__ == "__main__": main()
