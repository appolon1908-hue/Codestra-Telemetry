from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "development_lock", ROOT / "scripts/validate_repository_development_lock.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
sys.path.insert(0, str(ROOT / "scripts"))
REMOTE_SPEC = importlib.util.spec_from_file_location(
    "development_lock_remote",
    ROOT / "scripts/verify_repository_development_lock_remote.py",
)
assert REMOTE_SPEC and REMOTE_SPEC.loader
REMOTE = importlib.util.module_from_spec(REMOTE_SPEC)
REMOTE_SPEC.loader.exec_module(REMOTE)


class RepositoryDevelopmentLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = VALIDATOR.load(VALIDATOR.LOCK_PATH)
        self.inventory = VALIDATOR.load(VALIDATOR.INVENTORY_PATH)

    def test_accepts_authoritative_snapshot(self) -> None:
        VALIDATOR.validate(self.lock, self.inventory)

    def test_current_refresh_pins_exact_protected_development_heads(self) -> None:
        locked = {
            entry["serviceId"]: (
                entry["developmentSha"],
                entry["successfulProtectedPushRuns"],
            )
            for entry in self.lock["repositories"]
        }
        self.assertEqual(
            locked["opentelemetry"],
            ("81552819fd16f8275b5711cd882347b605b3f5a3", 5),
        )
        self.assertEqual(
            locked["prometheus"],
            ("e45cf15cd71e5ade8e11e58771b6c480bb32a003", 2),
        )
        self.assertEqual(
            locked["alloy"],
            ("f4c4e6b19e6274578a97e1db0ca85e32339a2062", 2),
        )
        self.assertEqual(
            locked["superset"],
            ("d656a0eac2f8c335519e2ed3da2bd19046a54fbe", 6),
        )

    def test_rejects_activation(self) -> None:
        lock = copy.deepcopy(self.lock)
        lock["productionActivation"] = True
        with self.assertRaises(ValueError):
            VALIDATOR.validate(lock, self.inventory)

    def test_rejects_duplicate_component(self) -> None:
        lock = copy.deepcopy(self.lock)
        lock["repositories"][1]["serviceId"] = lock["repositories"][0]["serviceId"]
        with self.assertRaises(ValueError):
            VALIDATOR.validate(lock, self.inventory)

    def test_rejects_non_successful_check(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["repositories"][0]["checkConclusions"]["validate"] = "FAILURE"
        with self.assertRaises(ValueError):
            VALIDATOR.validate(self.lock, inventory)

    def test_rejects_unresolved_review(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        inventory["repositories"][0]["unresolvedReviewThreadCount"] = 1
        with self.assertRaises(ValueError):
            VALIDATOR.validate(self.lock, inventory)

    def test_rejects_merging_unsafe_postgres_pr(self) -> None:
        inventory = copy.deepcopy(self.inventory)
        postgres = next(
            item
            for item in inventory["repositories"]
            if item["repository"].endswith("Codestra-Postgres-Exporter")
        )
        postgres["merged"] = True
        with self.assertRaises(ValueError):
            VALIDATOR.validate(self.lock, inventory)

    def test_remote_run_selection_requires_protected_branch(self) -> None:
        runs = [
            {"event": "push", "head_branch": "feature/example"},
            {"event": "pull_request", "head_branch": "development"},
            {"event": "push", "head_branch": "development"},
        ]
        self.assertEqual(
            REMOTE.protected_push_runs(runs, "development"),
            [{"event": "push", "head_branch": "development"}],
        )

    def test_remote_merge_ancestry_is_fail_closed(self) -> None:
        self.assertTrue(REMOTE.merge_is_ancestor({"status": "ahead"}))
        self.assertTrue(REMOTE.merge_is_ancestor({"status": "identical"}))
        self.assertFalse(REMOTE.merge_is_ancestor({"status": "diverged"}))
        self.assertFalse(REMOTE.merge_is_ancestor({"status": "behind"}))
        self.assertFalse(REMOTE.merge_is_ancestor({}))

    def test_remote_postgres_supersession_binds_exact_pr(self) -> None:
        observed = {
            "supersedingPullRequest": 7,
            "supersedingHeadSha": "1" * 40,
            "supersedingMergeSha": "2" * 40,
        }
        pull = {
            "state": "closed",
            "merged": True,
            "draft": False,
            "number": 7,
            "head": {"sha": "1" * 40},
            "base": {"ref": "development"},
            "merge_commit_sha": "2" * 40,
        }
        self.assertTrue(REMOTE.postgres_supersession_matches(pull, observed))
        pull["head"] = {"sha": "3" * 40}
        self.assertFalse(REMOTE.postgres_supersession_matches(pull, observed))

    def test_workflow_grants_remote_evidence_read_scopes(self) -> None:
        workflow = (
            ROOT / ".github/workflows/validate-repository-development-lock.yml"
        ).read_text()
        for scope in ("actions", "checks", "contents", "pull-requests", "statuses"):
            self.assertIn(f"  {scope}: read", workflow)

    def test_workflow_binds_promoted_branches_to_development_tree(self) -> None:
        workflow = (
            ROOT / ".github/workflows/validate-repository-development-lock.yml"
        ).read_text()
        for statement in (
            'HEAD_BRANCH: ${{ github.event.pull_request.head.ref }}',
            '"$HEAD_BRANCH" =~ ^(test|staging|production|main)$',
            'remote_development="$(gh api "repos/${GITHUB_REPOSITORY}/branches/development" --jq',
            'git rev-parse "${HEAD_SHA}^{tree}"',
            'git rev-parse "${remote_development}^{tree}"',
            'git checkout --detach "$remote_development"',
            'git checkout --detach "$HEAD_SHA"',
            'PROTECTED_BRANCH: ${{ github.ref_name }}',
            '"$PROTECTED_BRANCH" != "development"',
        ):
            self.assertIn(statement, workflow)
        self.assertNotIn("--force", workflow)

    def test_lock_document_records_remote_and_rollback_contracts(self) -> None:
        documentation = " ".join(
            (ROOT / "docs/REPOSITORY-DEVELOPMENT-LOCK.md").read_text().split()
        )
        for statement in (
            "protected `development` branch",
            "ancestor",
            "PostgreSQL Exporter PR #7",
            "does not publish or deploy an image",
            "Rollback",
        ):
            self.assertIn(statement, documentation)


if __name__ == "__main__":
    unittest.main()
