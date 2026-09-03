from __future__ import annotations

import json
import copy
import importlib.util
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "repository_authority", ROOT / "scripts/validate_repository_authority.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


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

    def test_upstream_identity_is_exact(self) -> None:
        authority = json.loads((ROOT / "CODESTRA_UPSTREAM.json").read_text())
        lock = json.loads((ROOT / "CODESTRA_UPSTREAM_LOCK.json").read_text())
        VALIDATOR.validate_upstream_metadata(authority, lock)
        redirected = copy.deepcopy(authority)
        redirected["upstream_clone_url"] = "https://github.com/example/other.git"
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_upstream_metadata(redirected, lock)

    def test_upstream_lock_cannot_disagree_with_authority(self) -> None:
        authority = json.loads((ROOT / "CODESTRA_UPSTREAM.json").read_text())
        lock = json.loads((ROOT / "CODESTRA_UPSTREAM_LOCK.json").read_text())
        lock["upstream_ref"] = "other"
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_upstream_metadata(authority, lock)

    def test_source_and_image_manifests_cannot_activate_production(self) -> None:
        self.assertFalse(json.loads((ROOT / "CODESTRA_UPSTREAM.json").read_text())["deployment_enabled"])
        for relative in (
            "codestra/release/image-build.v1.json",
            "codestra/control-api/release/image-build.v1.json",
        ):
            manifest = json.loads((ROOT / relative).read_text())
            self.assertFalse(manifest["productionActivation"])
            self.assertTrue(manifest["embedSourceRevision"])

    def test_secret_scan_exceptions_are_exact_test_fixtures(self) -> None:
        config = (ROOT / ".gitleaks.toml").read_text()
        paths = re.findall(r"(?m)^\s*'''([^']+)''',?\s*$", config)
        self.assertEqual(len(paths), 9)
        self.assertTrue(all(path.startswith("^upstream/") and path.endswith("$") for path in paths))
        self.assertTrue(all("testdata/" in path for path in paths))


if __name__ == "__main__":
    unittest.main()
