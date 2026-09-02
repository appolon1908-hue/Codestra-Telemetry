from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collector_runtime_identity",
    ROOT / "scripts/validate_collector_runtime_identity.py",
)
assert SPEC and SPEC.loader
RUNTIME_IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME_IDENTITY)


class CollectorRuntimeIdentityTest(unittest.TestCase):
    def values(self, digest: str = "2" * 64) -> dict[str, str]:
        return {
            "CODESTRA_OTELCOL_IMAGE": (
                "ghcr.io/appolon1908-hue/codestra-telemetry-opentelemetry@sha256:"
                + digest
            ),
            "CODESTRA_SOURCE_SHA": "0" * 40,
            "CODESTRA_IMAGE_DIGEST": "sha256:" + digest,
        }

    def test_accepts_aligned_immutable_identity(self) -> None:
        inspection = mock.Mock(returncode=0, stdout="0" * 40 + "\n")
        with mock.patch.dict(os.environ, self.values(), clear=True), mock.patch.object(
            RUNTIME_IDENTITY.subprocess, "run", return_value=inspection
        ) as run:
            RUNTIME_IDENTITY.main()
        run.assert_called_once()

    def test_rejects_digest_mismatch(self) -> None:
        values = self.values()
        values["CODESTRA_IMAGE_DIGEST"] = "sha256:" + "3" * 64
        with mock.patch.dict(os.environ, values, clear=True):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()

    def test_rejects_source_revision_readback_mismatch(self) -> None:
        inspection = mock.Mock(returncode=0, stdout="1" * 40 + "\n")
        with mock.patch.dict(os.environ, self.values(), clear=True), mock.patch.object(
            RUNTIME_IDENTITY.subprocess, "run", return_value=inspection
        ):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()

    def test_rejects_mutable_image(self) -> None:
        values = self.values()
        values["CODESTRA_OTELCOL_IMAGE"] = "opentelemetry:latest"
        with mock.patch.dict(os.environ, values, clear=True):
            with self.assertRaises(SystemExit):
                RUNTIME_IDENTITY.main()


if __name__ == "__main__":
    unittest.main()
