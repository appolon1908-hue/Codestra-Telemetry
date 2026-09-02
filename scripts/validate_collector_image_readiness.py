#!/usr/bin/env python3
"""Validate repository-only signed-image readiness for the Collector."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
AUTHORITY = (
    "appolon1908-hue/Codestra-Telemetry/.github/workflows/"
    "reusable-release-image.yml@c327aed6cb43072f5367cd4c52639a901c54e114"
)
REQUIRED = (
    "REPOSITORY_PROFILE.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    "docs/BACKUP_RESTORE_ROLLBACK.md",
    "docs/UPGRADE.md",
    ".dockerignore",
    "codestra/collector.yaml",
    "codestra/deploy/Dockerfile",
    "codestra/release/image-build.v1.json",
    "codestra/release/runtime-base.lock.json",
    "codestra/compose.candidate.yaml",
    "codestra/runtime.env.example",
    ".github/workflows/release-collector-image.yml",
    "scripts/build_and_inspect_collector_image.sh",
    "scripts/validate_collector_runtime_identity.py",
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
        fail(f"missing Collector readiness files: {missing}")

    manifest = load("codestra/release/image-build.v1.json")
    lock = load("codestra/release/runtime-base.lock.json")
    if (
        manifest.get("imageId") != "opentelemetry"
        or manifest.get("embedSourceRevision") is not True
        or manifest.get("dockerfile") != "codestra/deploy/Dockerfile"
        or manifest.get("context") != "."
        or manifest.get("productionActivation") is not False
    ):
        fail("Collector image manifest identity/context/activation mismatch")
    if (
        lock.get("artifactModel") != "repository-configured-signed-image"
        or lock.get("imageId") != "opentelemetry"
        or lock.get("productionActivation") is not False
        or lock.get("upstreamSignedTagsVerified") is not True
        or lock.get("vendoredSourceExecutableUsed") is not False
    ):
        fail("Collector runtime lock identity/model/activation mismatch")
    for field in ("buildFrontendImage", "builderImage", "upstreamImage"):
        if not IMAGE.fullmatch(str(lock.get(field, ""))):
            fail(f"mutable Collector build input: {field}")
    for field in (
        "builderLinuxAmd64Manifest",
        "upstreamLinuxAmd64Manifest",
        "upstreamReleaseLinuxAmd64ArchiveSha256",
    ):
        if not DIGEST.fullmatch(str(lock.get(field, ""))):
            fail(f"missing linux/amd64 platform digest: {field}")
    for field in ("upstreamReleaseCommit", "upstreamContribCommit"):
        if not SHA.fullmatch(str(lock.get(field, ""))):
            fail(f"missing exact upstream source authority: {field}")
    if lock.get("upstreamRelease") != "0.159.0":
        fail("Collector upstream version mismatch")
    expected_args = {
        "GO_BUILDER_IMAGE": lock["builderImage"],
        "OTELCOL_BASE_IMAGE": lock["upstreamImage"],
    }
    if manifest.get("buildArgs") != expected_args:
        fail("Collector image build arguments differ from the runtime lock")

    dockerfile = (ROOT / manifest["dockerfile"]).read_text(encoding="utf-8")
    if dockerfile.splitlines()[0] != f"# syntax={lock['buildFrontendImage']}":
        fail("Collector Dockerfile frontend differs from the runtime lock")
    for token in (
        "FROM ${GO_BUILDER_IMAGE} AS healthcheck-builder",
        "FROM ${OTELCOL_BASE_IMAGE}",
        "ARG CODESTRA_SOURCE_SHA",
        "ENV CODESTRA_IMAGE_SOURCE_SHA=${CODESTRA_SOURCE_SHA}",
        "-buildvcs=false",
        "-buildid=",
        "/otelcol-healthcheck",
        "/etc/otelcol-contrib/config.yaml",
        "/usr/share/codestra/runtime-base.lock.json",
        "USER 10001:10001",
    ):
        if token not in dockerfile:
            fail(f"Collector build boundary missing: {token}")
    healthcheck = (ROOT / "codestra/deploy/healthcheck.go").read_text(encoding="utf-8")
    if "http://127.0.0.1:13133/" not in healthcheck or "Getenv" in healthcheck:
        fail("Collector image health probe must be bounded to loopback")

    compose_text = (ROOT / "codestra/compose.candidate.yaml").read_text(
        encoding="utf-8"
    )
    compose = yaml.safe_load(compose_text)
    service = compose.get("services", {}).get("otel-collector", {})
    if (
        "build" in service
        or "ports" in service
        or service.get("privileged") is True
        or service.get("network_mode") == "host"
        or service.get("pid") == "host"
    ):
        fail("Collector candidate has a build, public, or host-authority path")
    if service.get("profiles") != ["candidate-after-approval"]:
        fail("Collector candidate must remain inactive by default")
    if service.get("read_only") is not True or service.get("user") != "10001:10001":
        fail("Collector candidate must be read-only and non-root")
    if service.get("pull_policy") != "never" or "ALL" not in service.get("cap_drop", []):
        fail("Collector candidate must use the pre-pulled image and drop capabilities")
    if service.get("environment", {}).get("CODESTRA_BUSINESS") != "platform":
        fail("Collector business identity must be repository-controlled")
    if service.get("labels", {}).get("codestra.business") != "platform":
        fail("Collector business label must be repository-controlled")
    if service.get("image") != "${CODESTRA_OTELCOL_IMAGE:?immutable Codestra Collector image with sha256 digest is required}":
        fail("Collector candidate image input is not fail-closed")
    if service.get("ports") or set(service.get("networks", {})) != {
        "codestra-business-telemetry",
        "codestra-observability",
    }:
        fail("Collector candidate private network boundary mismatch")
    secrets = compose.get("secrets", {})
    if set(secrets) != {
        "otelcol_server_cert",
        "otelcol_server_key",
        "otelcol_client_ca",
        "otelcol_backend_ca",
    } or any(set(value) != {"file"} for value in secrets.values()):
        fail("Collector credentials must use exactly the mounted secret files")
    if "latest" in compose_text.lower() or "env_file" in compose_text:
        fail("Collector candidate contains a mutable image or credential environment file")
    runtime_example = (ROOT / "codestra/runtime.env.example").read_text(encoding="utf-8")
    if re.search(r"(?m)^CODESTRA_BUSINESS=", runtime_example):
        fail("Collector runtime example may not expose caller-controlled business identity")

    identity_source = (ROOT / "scripts/validate_collector_runtime_identity.py").read_text(
        encoding="utf-8"
    )
    for token in (
        '"docker",',
        '"image",',
        '"inspect",',
        "org.opencontainers.image.revision",
        "image_revision != source_sha",
        "CODESTRA_IMAGE_SOURCE_SHA=",
        "embedded != [f\"CODESTRA_IMAGE_SOURCE_SHA={source_sha}\"]",
        "stderr=subprocess.DEVNULL",
    ):
        if token not in identity_source:
            fail(f"Collector runtime source-to-image read-back binding missing: {token}")
    build_inspection = (ROOT / "scripts/build_and_inspect_collector_image.sh").read_text(
        encoding="utf-8"
    )
    if '--label "org.opencontainers.image.revision=$source_sha"' not in build_inspection:
        fail("exact local Collector image build must apply the OCI source revision label")
    for token in (
        '--build-arg "CODESTRA_SOURCE_SHA=$source_sha"',
        'test "$embedded_source" = "CODESTRA_IMAGE_SOURCE_SHA=$source_sha"',
    ):
        if token not in build_inspection:
            fail(f"exact local Collector image build lacks source embedding: {token}")

    release = yaml.safe_load(
        (ROOT / ".github/workflows/release-collector-image.yml").read_text(
            encoding="utf-8"
        )
    )
    job = release.get("jobs", {}).get("release", {})
    if job.get("uses") != AUTHORITY:
        fail("Collector release workflow authority mismatch")
    if job.get("with", {}) != {
        "image_id": "opentelemetry",
        "release_tag": "${{ inputs.release_tag }}",
        "protected_source_sha": "${{ inputs.protected_source_sha }}",
        "build_manifest_path": "codestra/release/image-build.v1.json",
    }:
        fail("Collector release workflow inputs mismatch")

    build_calls = {
        ".github/workflows/validate-collector-image-readiness.yml": (
            'bash scripts/build_and_inspect_collector_image.sh "$HEAD_SHA"',
            'bash scripts/build_and_inspect_collector_image.sh "$GITHUB_SHA"',
        ),
        ".github/workflows/validate-collector-image-readiness-protected.yml": (
            'bash scripts/build_and_inspect_collector_image.sh "$GITHUB_SHA"',
        ),
    }
    for relative, required_calls in build_calls.items():
        workflow_source = (ROOT / relative).read_text(encoding="utf-8")
        if any(call not in workflow_source for call in required_calls):
            fail(f"exact Collector image build missing: {relative}")

    for workflow in (ROOT / ".github/workflows").glob("*.yml"):
        source = workflow.read_text(encoding="utf-8")
        for reference in re.findall(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)", source):
            if not reference.startswith("./") and not re.fullmatch(
                r"[^@\s]+@[0-9a-f]{40}", reference
            ):
                fail(f"mutable action: {workflow.name}: {reference}")
        if re.search(
            r"git push\s+origin\s+HEAD:(?:main|development|test|staging|production)",
            source,
        ):
            fail(f"direct protected-branch push: {workflow.name}")

    print("COLLECTOR_IMAGE_READINESS=PASS")
    print("ARTIFACT_MODEL=SIGNED_IMAGE")
    print("PRODUCTION_ACTIVATION=NO")


if __name__ == "__main__":
    main()
