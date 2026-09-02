from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryAuthorityTests(unittest.TestCase):
    def test_validator(self) -> None:
        subprocess.run(
            ["python3", "scripts/validate_repository_authority.py"],
            cwd=ROOT,
            check=True,
        )

    def test_imported_tree_is_exact(self) -> None:
        lock = json.loads((ROOT / "CODESTRA_UPSTREAM_LOCK.json").read_text())
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD:upstream"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(tree, lock["imported_tree_sha"])

    def test_source_and_image_manifests_cannot_activate_production(self) -> None:
        self.assertFalse(json.loads((ROOT / "CODESTRA_UPSTREAM.json").read_text())["deployment_enabled"])
        for relative in (
            "codestra/release/image-build.v1.json",
            "codestra/control-api/release/image-build.v1.json",
        ):
            self.assertFalse(json.loads((ROOT / relative).read_text())["productionActivation"])


if __name__ == "__main__":
    unittest.main()
