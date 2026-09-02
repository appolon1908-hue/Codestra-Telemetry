from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_validator", ROOT / "scripts/validate_reusable_config_release.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ReusableReleaseAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = VALIDATOR.WORKFLOW.read_text(encoding="utf-8")

    def test_committed_workflow_passes(self) -> None:
        VALIDATOR.validate(self.source)

    def test_mutable_action_is_rejected(self) -> None:
        source = self.source.replace(
            "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
            "actions/checkout@v4",
        )
        with self.assertRaisesRegex(ValueError, "mutable action"):
            VALIDATOR.validate(source)

    def test_removed_production_lineage_gate_is_rejected(self) -> None:
        source = self.source.replace(
            'test "$(git rev-parse origin/production)" = "$SOURCE_SHA"', "true"
        )
        with self.assertRaisesRegex(ValueError, "origin/production"):
            VALIDATOR.validate(source)

    def test_removed_caller_production_ref_gate_is_rejected(self) -> None:
        source = self.source.replace(
            'test "$GITHUB_REF" = "refs/heads/production"', "true"
        )
        with self.assertRaisesRegex(ValueError, "refs/heads/production"):
            VALIDATOR.validate(source)

    def test_latest_tool_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutable latest"):
            VALIDATOR.validate(self.source + "\n# tool:latest\n")


if __name__ == "__main__":
    unittest.main()
