from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "development_lock", ROOT / "scripts/validate_repository_development_lock.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RepositoryDevelopmentLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lock = VALIDATOR.load(VALIDATOR.LOCK_PATH)
        self.inventory = VALIDATOR.load(VALIDATOR.INVENTORY_PATH)

    def test_accepts_authoritative_snapshot(self) -> None:
        VALIDATOR.validate(self.lock, self.inventory)

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


if __name__ == "__main__":
    unittest.main()
