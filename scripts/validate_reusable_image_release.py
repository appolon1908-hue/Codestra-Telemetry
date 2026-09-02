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
    "push-by-digest=true", "job_workflow_ref", "job_workflow_sha",
    "--signer-repo appolon1908-hue/Codestra-Telemetry",
    "--signer-workflow appolon1908-hue/Codestra-Telemetry/.github/workflows/reusable-release-image.yml",
    "concurrency:", "cancel-in-progress: false",
    "Publish immutable release label after every gate passes",
    'gitleaks dir --no-banner --redact=100 --exit-code 1 "$context"',
    "Dockerfile frontend must be pinned by exact sha256 digest",
    "uncontrolled external COPY source",
    "duplicate JSON key in image build manifest",
)
def validate(source: str) -> None:
    for token in REQUIRED:
        if token not in source: raise ValueError(f"reusable image release missing: {token}")
    for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", source):
        if not reference.startswith("./") and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", reference):
            raise ValueError(f"mutable action reference: {reference}")
    if "calling_workflow_path" in source:
        raise ValueError("caller-controlled signing workflow identity is prohibited")
    upload = source.find("actions/upload-artifact@")
    publish = source.find("Publish immutable release label after every gate passes")
    if upload < 0 or publish < 0 or publish <= upload:
        raise ValueError("release label must be published only after evidence upload")
    if '--tag "${REGISTRY}:${RELEASE_TAG}"' in source:
        raise ValueError("build may not publish the human release label before gates pass")
def main() -> None:
    validate(WORKFLOW.read_text()); print("REUSABLE_IMAGE_RELEASE_AUTHORITY=PASS"); print("PRODUCTION_DEPLOYED=NO")
if __name__ == "__main__": main()
