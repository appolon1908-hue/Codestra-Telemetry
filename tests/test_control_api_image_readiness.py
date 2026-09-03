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
READINESS_SPEC = importlib.util.spec_from_file_location(
    "control_api_image_readiness",
    ROOT / "scripts/validate_control_api_image_readiness.py",
)
assert READINESS_SPEC and READINESS_SPEC.loader
READINESS = importlib.util.module_from_spec(READINESS_SPEC)
READINESS_SPEC.loader.exec_module(READINESS)


class RuntimeIdentityTest(unittest.TestCase):
    def test_release_manifest_parser_rejects_duplicate_keys(self) -> None:
        with self.assertRaises(SystemExit):
            READINESS.unique_object([("embedSourceRevision", True), ("embedSourceRevision", False)])

    def test_server_validates_embedded_identity_before_configuration(self) -> None:
        main = (ROOT / "codestra/control-api/cmd/codestra-observability-api/main.go").read_text()
        identity = (ROOT / "codestra/control-api/internal/runtimeidentity/identity.go").read_text()
        self.assertLess(main.index("runtimeidentity.ValidateEnvironment()"), main.index("controlapi.LoadRegistry"))
        self.assertIn("embeddedSourcePath", identity)
        healthcheck = (ROOT / "codestra/control-api/cmd/healthcheck/main.go").read_text()
        self.assertIn('[]string{"/healthz", "/readyz"}', healthcheck)

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
        revision = mock.Mock(returncode=0, stdout="0" * 40 + "\n")
        embedded = mock.Mock(
            returncode=0, stdout="CODESTRA_IMAGE_SOURCE_SHA=" + "0" * 40 + "\n"
        )
        with mock.patch.dict(os.environ, values, clear=True), mock.patch.object(
            RUNTIME_IDENTITY.subprocess, "run", side_effect=[revision, embedded]
        ) as run:
            RUNTIME_IDENTITY.main()
        self.assertEqual(run.call_count, 2)

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

    def test_rejects_source_revision_readback_mismatch(self) -> None:
        digest = "2" * 64
        values = {
            "CODESTRA_CONTROL_API_IMAGE": (
                "ghcr.io/appolon1908-hue/codestra-telemetry-control-api@sha256:"
                + digest
            ),
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + digest,
        }
        inspection = mock.Mock(returncode=0, stdout="1" * 40 + "\n")
        with mock.patch.dict(os.environ, values, clear=True), mock.patch.object(
            RUNTIME_IDENTITY.subprocess, "run", return_value=inspection
        ):
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

    def test_rejects_embedded_source_mismatch(self) -> None:
        digest = "2" * 64
        values = {
            "CODESTRA_CONTROL_API_IMAGE": (
                "ghcr.io/appolon1908-hue/codestra-telemetry-control-api@sha256:"
                + digest
            ),
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + digest,
        }
        revision = mock.Mock(returncode=0, stdout="0" * 40 + "\n")
        embedded = mock.Mock(
            returncode=0, stdout="CODESTRA_IMAGE_SOURCE_SHA=" + "1" * 40 + "\n"
        )
        with mock.patch.dict(os.environ, values, clear=True), mock.patch.object(
            RUNTIME_IDENTITY.subprocess,
            "run",
            side_effect=[revision, embedded],
        ):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()


if __name__ == "__main__":
    unittest.main()
