"""Middleware V3 trace pipeline: propagation preserved, every credential class scrubbed, contract dark."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_middleware_v3_trace_pipeline", ROOT / "scripts" / "validate_middleware_v3_trace_pipeline.py"
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class TracePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = VALIDATOR.load_yaml(VALIDATOR.AGENT)
        cls.gateway = VALIDATOR.load_yaml(VALIDATOR.GATEWAY)
        cls.contract = json.loads(VALIDATOR.CONTRACT.read_text(encoding="utf-8"))
        cls.keys = VALIDATOR.key_patterns(cls.agent)

    def test_source_passes(self) -> None:
        VALIDATOR.validate_keys(self.keys)
        VALIDATOR.validate_values(self.agent)
        VALIDATOR.validate_propagation(self.agent, self.gateway)
        VALIDATOR.validate_contract(self.contract, self.agent)

    def test_pins(self) -> None:
        self.assertEqual(self.contract["middleware"]["prep_base_sha"], "22d023a9c65b0789a0f7ee6c28548753521a9eff")
        self.assertEqual(self.contract["middleware"]["v3_final_sha"], "PENDING")
        self.assertEqual(self.contract["status"], "PREPARED_DISABLED")

    def test_compound_credential_keys_are_deleted_and_drilldown_keys_kept(self) -> None:
        deleted = ("smtp_password", "provider_api_key", "x-api-key", "bao_token", "klyrow_client_secret", "postgres_dsn", "aws_secret_access_key")
        for key in deleted:
            self.assertTrue(any(p.search(key) for p in self.keys), key)
            self.assertTrue(any(p.search(key.upper()) for p in self.keys), key)
        for key in ("correlation.id", "codestra.operation.id", "openbao.secret_ref", "codestra.token_type", "deployment.id", "codestra.token_count"):
            self.assertFalse(any(p.search(key) for p in self.keys), key)

    def test_secret_shapes_scrubbed_in_span_and_log_values(self) -> None:
        for signal in ("trace", "log"):
            rules = VALIDATOR.statements(self.agent, signal)
            for value, secret in (
                ("Authorization Basic UExBTlRFRFBBU1NQTEFOVEVE", "UExBTlRFRFBBU1NQTEFOVEVE"),
                ("postgres://mw:PLANTEDPASS@postgres/mw", "PLANTEDPASS"),
                ("redis://:PLANTEDPASS@redis:6379", "PLANTEDPASS"),
                ("hvs." + "A" * 30, "hvs." + "A" * 30),
                ("s." + "c" * 26, "s." + "c" * 26),
                ("b." + "d" * 70, "b." + "d" * 70),
                ("eyJ" + "a" * 20 + "." + "eyJ" + "b" * 20 + "." + "c" * 30, "eyJ" + "a" * 20),
                ("-----BEGIN EC PRIVATE KEY-----\nPLANTEDKEY\n-----END EC PRIVATE KEY-----", "PLANTEDKEY"),
            ):
                self.assertNotIn(secret, VALIDATOR.scrub(value, rules, "value"), (signal, value))

    def test_log_body_key_value_credentials_scrubbed(self) -> None:
        rules = VALIDATOR.statements(self.agent, "log")
        for body, secret, kept in (
            ("SMTP_PASSWORD=PLANTED1 host=smtp", "PLANTED1", "host=smtp"),
            ("provider_api_key: PLANTED2 provider=klyrow", "PLANTED2", "provider=klyrow"),
            ("client_secret=PLANTED3 client_id=middleware-api", "PLANTED3", "client_id=middleware-api"),
            ("operation_id=op-1 secret_ref=codestra/production/middleware/api/database token_count=3", "", "secret_ref=codestra/production/middleware/api/database"),
        ):
            result = VALIDATOR.scrub(body, rules, "body")
            if secret:
                self.assertNotIn(secret, result, body)
            self.assertIn(kept, result, body)

    def test_trace_context_is_never_rewritten(self) -> None:
        rendered = json.dumps(self.agent["processors"]) + json.dumps(self.gateway["processors"])
        self.assertNotRegex(rendered, r'set\((trace_id|span_id|parent_span_id)\b')
        self.assertEqual(self.contract["propagation"]["headers"], ["traceparent", "tracestate"])

    def test_v3_span_coverage_uses_only_safe_attributes(self) -> None:
        stages = [span["stage"] for span in self.contract["v3_span_coverage"]]
        self.assertEqual(stages, VALIDATOR.V3_STAGES)
        forbidden = set(self.contract["forbidden_span_attributes"])
        for span in self.contract["v3_span_coverage"]:
            for attribute in span["attributes"]:
                self.assertNotIn(attribute, forbidden)
                self.assertFalse(any(p.search(attribute) for p in self.keys), attribute)

    def test_contract_rejects_activation_and_drift(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["activation_enabled"] = True
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.agent)
        mutated = copy.deepcopy(self.contract)
        mutated["v3_span_coverage"][0]["attributes"].append("authorization")
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.agent)
        mutated = copy.deepcopy(self.contract)
        mutated["propagation"]["headers"] = ["traceparent"]
        with self.assertRaises(SystemExit):
            VALIDATOR.validate_contract(mutated, self.agent)


if __name__ == "__main__":
    unittest.main()
