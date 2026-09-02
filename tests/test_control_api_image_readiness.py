from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "runtime_identity", ROOT / "scripts/validate_control_api_runtime_identity.py"
)
assert SPEC and SPEC.loader
RUNTIME_IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_IDENTITY)


class RuntimeIdentityTest(unittest.TestCase):
    def test_accepts_aligned_immutable_identity(self) -> None:
        digest = "2" * 64
        values = {
            "CODESTRA_CONTROL_API_IMAGE": (
                "ghcr.io/appolon1908-hue/codestra-telemetry-control-api@sha256:"
                + digest
            ),
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + digest,
        }
        with mock.patch.dict(os.environ, values, clear=True):
            RUNTIME_IDENTITY.main()

    def test_rejects_digest_mismatch(self) -> None:
        values = {
            "CODESTRA_CONTROL_API_IMAGE": (
                "ghcr.io/appolon1908-hue/codestra-telemetry-control-api@sha256:"
                + "2" * 64
            ),
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + "3" * 64,
        }
        with mock.patch.dict(os.environ, values, clear=True):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()

    def test_rejects_mutable_image(self) -> None:
        values = {
            "CODESTRA_CONTROL_API_IMAGE": "control-api:latest",
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + "2" * 64,
        }
        with mock.patch.dict(os.environ, values, clear=True):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()


if __name__ == "__main__":
    unittest.main()
