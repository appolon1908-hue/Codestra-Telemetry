from __future__ import annotations
import importlib.util, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validator", ROOT / "scripts/validate_reusable_image_release.py"); assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(VALIDATOR)
class ImageReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None: cls.source = VALIDATOR.WORKFLOW.read_text()
    def test_committed_workflow(self) -> None: VALIDATOR.validate(self.source)
    def test_mutable_action(self) -> None:
        source = self.source.replace("actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "actions/checkout@v4")
        with self.assertRaisesRegex(ValueError, "mutable action"): VALIDATOR.validate(source)
    def test_production_ref_gate(self) -> None:
        source = self.source.replace('test "$GITHUB_REF" = "refs/heads/production"', "true")
        with self.assertRaisesRegex(ValueError, "refs/heads/production"): VALIDATOR.validate(source)
    def test_revision_label_gate(self) -> None:
        source = self.source.replace("org.opencontainers.image.revision", "removed.revision")
        with self.assertRaisesRegex(ValueError, "revision"): VALIDATOR.validate(source)
    def test_caller_controlled_signer_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "caller-controlled"):
            VALIDATOR.validate(self.source + "\ncalling_workflow_path: unsafe.yml\n")
    def test_release_label_must_follow_evidence_upload(self) -> None:
        source = self.source.replace(
            "Publish immutable release label after every gate passes",
            "removed release publication step",
        )
        with self.assertRaisesRegex(ValueError, "release label"):
            VALIDATOR.validate(source)
    def test_early_release_tag_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "before gates"):
            VALIDATOR.validate(self.source + '\n--tag "${REGISTRY}:${RELEASE_TAG}"\n')
    def test_frontend_digest_gate_is_present(self) -> None:
        source = self.source.replace(
            "Dockerfile frontend must be pinned by exact sha256 digest",
            "frontend gate removed",
        )
        with self.assertRaisesRegex(ValueError, "frontend"):
            VALIDATOR.validate(source)
    def test_external_copy_gate_is_present(self) -> None:
        source = self.source.replace(
            "uncontrolled external COPY source",
            "external copy gate removed",
        )
        with self.assertRaisesRegex(ValueError, "COPY"):
            VALIDATOR.validate(source)
if __name__ == "__main__": unittest.main()
