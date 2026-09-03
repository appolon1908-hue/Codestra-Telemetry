#!/usr/bin/env python3
"""Fail closed unless control API runtime identity inputs are exact and aligned."""
from __future__ import annotations

import os
import re
import subprocess

IMAGE = re.compile(
    r"^ghcr\.io/appolon1908-hue/codestra-telemetry-control-api@sha256:([0-9a-f]{64})$"
)
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")


def fail(message: str) -> None:
    raise SystemExit(f"CONTROL_API_RUNTIME_IDENTITY=FAIL reason={message}")


def main() -> None:
    image = os.environ.get("CODESTRA_CONTROL_API_IMAGE", "")
    source_sha = os.environ.get("CODESTRA_SOURCE_SHA", "")
    digest = os.environ.get("CODESTRA_IMAGE_DIGEST", "")
    image_match = IMAGE.fullmatch(image)
    digest_match = DIGEST.fullmatch(digest)
    if not image_match:
        fail("image must use the immutable control API release repository and digest")
    if not SHA.fullmatch(source_sha):
        fail("source SHA must be 40 lowercase hexadecimal characters")
    if not digest_match or digest_match.group(1) != image_match.group(1):
        fail("image digest read-back must equal the image reference digest")
    result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            '{{index .Config.Labels "org.opencontainers.image.revision"}}',
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=15,
    )
    image_revision = result.stdout.strip()
    if result.returncode != 0 or not SHA.fullmatch(image_revision):
        fail("exact pulled image has no valid OCI source revision read-back")
    if image_revision != source_sha:
        fail("source SHA differs from exact pulled image OCI revision")
    env_result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{range .Config.Env}}{{println .}}{{end}}",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=15,
    )
    embedded = [
        line
        for line in env_result.stdout.splitlines()
        if line.startswith("CODESTRA_IMAGE_SOURCE_SHA=")
    ]
    if env_result.returncode != 0 or embedded != [f"CODESTRA_IMAGE_SOURCE_SHA={source_sha}"]:
        fail("exact pulled image does not embed its protected source SHA")
    print("CONTROL_API_RUNTIME_IDENTITY=PASS")


if __name__ == "__main__":
    main()
