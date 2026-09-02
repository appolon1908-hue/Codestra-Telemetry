#!/usr/bin/env python3
"""Validate repository-only signed-image readiness for the control API."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
AUTHORITY = (
    "appolon1908-hue/Codestra-Telemetry/.github/workflows/"
    "reusable-release-image.yml@37b8648bced4068b4287b39c9ff7a7174f0a9c28"
)
REQUIRED = (
    "REPOSITORY_PROFILE.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    "docs/BACKUP_RESTORE_ROLLBACK.md",
    "docs/UPGRADE.md",
    "codestra/control-api/.dockerignore",
    "codestra/control-api/release/image-build.v1.json",
    "codestra/control-api/release/runtime-base.lock.json",
    "codestra/control-api/compose.candidate.yaml",
    "codestra/control-api/runtime.env.example",
    ".github/workflows/release-control-api-image.yml",
    "scripts/build_and_inspect_control_api_image.sh",
    "scripts/validate_control_api_runtime_identity.py",
    "requirements-validation.txt",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path} must contain an object")
    return value


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing control API readiness files: {missing}")

    manifest = load("codestra/control-api/release/image-build.v1.json")
    lock = load("codestra/control-api/release/runtime-base.lock.json")
    if (
        manifest.get("imageId") != "control-api"
        or manifest.get("dockerfile") != "codestra/control-api/Dockerfile"
        or manifest.get("context") != "codestra/control-api"
        or manifest.get("productionActivation") is not False
    ):
        fail("control API image manifest identity/context/activation mismatch")
    if (
        lock.get("artifactModel") != "repository-built-signed-image"
        or lock.get("imageId") != "control-api"
        or lock.get("productionActivation") is not False
    ):
        fail("control API runtime lock identity/model/activation mismatch")
    for field in ("buildFrontendImage", "builderImage", "runtimeBaseImage"):
        if not IMAGE.fullmatch(str(lock.get(field, ""))):
            fail(f"mutable control API build input: {field}")
    for field in ("builderLinuxAmd64Manifest", "runtimeLinuxAmd64Manifest"):
        if not DIGEST.fullmatch(str(lock.get(field, ""))):
            fail(f"missing linux/amd64 platform digest: {field}")
    expected_args = {
        "GO_BUILDER_IMAGE": lock["builderImage"],
        "RUNTIME_IMAGE": lock["runtimeBaseImage"],
    }
    if manifest.get("buildArgs") != expected_args:
        fail("control API image build arguments differ from the runtime lock")

    dockerfile = (ROOT / manifest["dockerfile"]).read_text(encoding="utf-8")
    if dockerfile.splitlines()[0] != f"# syntax={lock['buildFrontendImage']}":
        fail("control API Dockerfile frontend differs from the runtime lock")
    for token in (
        "FROM ${GO_BUILDER_IMAGE} AS build",
        "FROM ${RUNTIME_IMAGE}",
        "-buildvcs=false",
        "-buildid=",
        "cmd/healthcheck",
        "USER 65532:65532",
        'CODESTRA_CONTROL_API_LISTEN_ADDRESS=127.0.0.1:8090',
        'CODESTRA_CONTROL_API_AUTH_MODE=required',
    ):
        if token not in dockerfile:
            fail(f"control API build boundary missing: {token}")

    compose_text = (ROOT / "codestra/control-api/compose.candidate.yaml").read_text(
        encoding="utf-8"
    )
    compose = yaml.safe_load(compose_text)
    service = compose.get("services", {}).get("control-api", {})
    if (
        "build" in service
        or "ports" in service
        or service.get("privileged") is True
        or service.get("network_mode") == "host"
        or service.get("pid") == "host"
    ):
        fail("control API candidate has a build, public, or host-authority path")
    if service.get("profiles") != ["candidate-after-approval"]:
        fail("control API candidate must remain inactive by default")
    if service.get("read_only") is not True or service.get("user") != "65532:65532":
        fail("control API candidate must be read-only and non-root")
    if "ALL" not in service.get("cap_drop", []):
        fail("control API candidate must drop all capabilities")
    environment = service.get("environment", {})
    if environment.get("CODESTRA_CONTROL_API_AUTH_MODE") != "required":
        fail("control API bearer authentication must be required")
    if environment.get("CODESTRA_CONTROL_API_BEARER_TOKEN_FILE") != "/run/secrets/control_api_bearer_token":
        fail("control API credential must be read from its mounted file")
    if environment.get("CODESTRA_CONTROL_API_LISTEN_ADDRESS") != "0.0.0.0:8090":
        fail("container listener must be available only on the private Compose network")
    if set(compose.get("secrets", {})) != {"control_api_bearer_token"}:
        fail("control API must declare exactly its bearer-token file")
    if any(set(value) != {"file"} for value in compose["secrets"].values()):
        fail("control API top-level secret must be a mounted file")
    if "latest" in compose_text.lower() or "env_file" in compose_text:
        fail("control API candidate contains a mutable image or credential environment file")

    release = yaml.safe_load(
        (ROOT / ".github/workflows/release-control-api-image.yml").read_text(
            encoding="utf-8"
        )
    )
    job = release.get("jobs", {}).get("release", {})
    if job.get("uses") != AUTHORITY:
        fail("control API release workflow authority mismatch")
    if job.get("with", {}) != {
        "image_id": "control-api",
        "release_tag": "${{ inputs.release_tag }}",
        "protected_source_sha": "${{ inputs.protected_source_sha }}",
        "build_manifest_path": "codestra/control-api/release/image-build.v1.json",
    }:
        fail("control API release workflow inputs mismatch")

    build_calls = {
        ".github/workflows/validate-control-api-image-readiness.yml": (
            'bash scripts/build_and_inspect_control_api_image.sh "$HEAD_SHA"',
            'bash scripts/build_and_inspect_control_api_image.sh "$GITHUB_SHA"',
        ),
        ".github/workflows/validate-control-api-image-readiness-protected.yml": (
            'bash scripts/build_and_inspect_control_api_image.sh "$GITHUB_SHA"',
        ),
    }
    for relative, required_calls in build_calls.items():
        workflow_source = (ROOT / relative).read_text(encoding="utf-8")
        if any(call not in workflow_source for call in required_calls):
            fail(f"exact control API image build missing: {relative}")

    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        text = workflow.read_text(encoding="utf-8")
        for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", text):
            if not reference.startswith("./") and not re.fullmatch(
                r"[^@\s]+@[0-9a-f]{40}", reference
            ):
                fail(f"mutable action: {workflow.name}: {reference}")
        if re.search(
            r"git push\s+origin\s+HEAD:(?:main|development|test|staging|production)",
            text,
        ):
            fail(f"direct protected-branch push: {workflow.name}")

    print("CONTROL_API_IMAGE_READINESS=PASS")
    print("ARTIFACT_MODEL=SIGNED_IMAGE")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
