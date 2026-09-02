#!/usr/bin/env python3
"""Source-only validation for the Codestra fourteen-authority control API."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "codestra" / "control-api"
REGISTRY_PATH = CONTROL / "config" / "services.json"
OPENAPI_PATH = CONTROL / "openapi.json"
DOCKERFILE_PATH = CONTROL / "Dockerfile"
SERVICE_CONTRACT_PATH = ROOT / "codestra" / "api" / "service-contract.v1.json"
SCHEMA_PATH = ROOT / "codestra" / "api" / "service-contract.schema.json"

EXPECTED = {
    "prometheus": "appolon1908-hue/Codestra-Prometheus",
    "grafana": "appolon1908-hue/Codestra-Grafana-",
    "alertmanager": "appolon1908-hue/Codestra-Alertmanager",
    "loki": "appolon1908-hue/Codestra-Loki",
    "tempo": "appolon1908-hue/Codestra-Tempo",
    "opentelemetry": "appolon1908-hue/Codestra-Telemetry",
    "alloy": "appolon1908-hue/Codestra-Alloy",
    "node-exporter": "appolon1908-hue/Codestra-Node-Exporter",
    "cadvisor": "appolon1908-hue/Codestra-cAdvisor",
    "redis-exporter": "appolon1908-hue/Codestra-Redis-Exporter",
    "postgres-exporter": "appolon1908-hue/Codestra-Postgres-Exporter",
    "blackbox-exporter": "appolon1908-hue/Codestra-Blackbox-Exporter",
    "superset": "appolon1908-hue/Superset",
    "openbao": "appolon1908-hue/Codestra-OpenBao",
}
REQUIRED_PATHS = {
    "/healthz",
    "/readyz",
    "/metrics",
    "/openapi.json",
    "/api/v1/capabilities",
    "/api/v1/services",
    "/api/v1/services/{serviceId}",
    "/api/v1/services/{serviceId}/health",
    "/api/v1/health",
    "/api/v1/topology",
    "/api/v1/contracts",
    "/api/v1/releases",
}
ENV_PATTERN = re.compile(r"^CODESTRA_[A-Z0-9_]+$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise ValueError(message)


def load(path: Path) -> Any:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    try:
        registry = load(REGISTRY_PATH)
        openapi = load(OPENAPI_PATH)
        load(SCHEMA_PATH)
        service_contract = load(SERVICE_CONTRACT_PATH)

        if registry.get("schemaVersion") != "1.0.0":
            fail("registry schemaVersion must be 1.0.0")
        if registry.get("expectedServiceCount") != 14:
            fail("registry expectedServiceCount must be 14")
        services = registry.get("services")
        if not isinstance(services, list) or len(services) != 14:
            fail("registry must contain exactly fourteen services")
        actual = {item.get("id"): item.get("repository") for item in services}
        if actual != EXPECTED:
            fail(f"registry service/repository map differs from authority catalogue: {actual}")

        schema_ref = registry.get("contractSchema", {})
        if schema_ref.get("repository") != "appolon1908-hue/Codestra-Telemetry":
            fail("registry contract schema repository is invalid")
        if schema_ref.get("path") != "codestra/api/service-contract.schema.json":
            fail("registry contract schema path is invalid")
        if schema_ref.get("version") != "1.0.0" or not GIT_SHA_PATTERN.fullmatch(schema_ref.get("sourceRevision", "")):
            fail("registry contract schema must use an immutable V1 Git revision")
        if service_contract.get("schemaAuthority") != schema_ref:
            fail("Telemetry service contract and registry must use the same schema authority")

        ids = set(EXPECTED)
        for service in services:
            if service.get("component") != service.get("id"):
                fail(f"component mismatch for {service.get('id')}")
            if service.get("deploymentClass") not in {"central", "agent"}:
                fail(f"invalid deployment class for {service.get('id')}")
            if service.get("nativeExposure") not in {"internal_private", "loopback_edge_only", "private_strong_auth"}:
                fail(f"invalid exposure for {service.get('id')}")
            if not ENV_PATTERN.fullmatch(service.get("baseUrlEnvironment", "")):
                fail(f"invalid baseUrlEnvironment for {service.get('id')}")
            release = service.get("release", {})
            for key in ("sourceRevisionEnvironment", "imageDigestEnvironment"):
                if not ENV_PATTERN.fullmatch(release.get(key, "")):
                    fail(f"invalid release environment for {service.get('id')}")
            contract = service.get("contract", {})
            if contract != {"path": "codestra/api/service-contract.v1.json", "version": "1.0.0"}:
                fail(f"invalid local contract reference for {service.get('id')}")
            for probe_name in ("health", "readiness"):
                probe = service.get(probe_name, {})
                if not isinstance(probe.get("path"), str) or not probe["path"].startswith("/") or probe["path"].startswith("//"):
                    fail(f"unsafe {probe_name} path for {service.get('id')}")
                statuses = probe.get("acceptedStatuses")
                if not isinstance(statuses, list) or not statuses or any(not isinstance(status, int) or not 100 <= status <= 599 for status in statuses):
                    fail(f"invalid {probe_name} statuses for {service.get('id')}")
            auth = service.get("auth", {})
            for value in auth.values():
                if not isinstance(value, str) or not ENV_PATTERN.fullmatch(value):
                    fail(f"auth registry values must be environment names for {service.get('id')}")
            if any(key.lower().endswith(("token", "password", "secret", "key")) for key in auth):
                fail(f"registry contains a raw credential field for {service.get('id')}")

        edges = registry.get("edges")
        if not isinstance(edges, list) or not edges:
            fail("registry topology edges are required")
        seen_edges: set[tuple[str, str, str]] = set()
        for edge in edges:
            if edge.get("from") not in ids or edge.get("to") not in ids:
                fail(f"topology edge references an unknown service: {edge}")
            if edge.get("from") == edge.get("to") or edge.get("mutating") is not False:
                fail(f"topology edge is unsafe: {edge}")
            identity = (edge["from"], edge["to"], edge.get("signal", ""))
            if identity in seen_edges:
                fail(f"duplicate topology edge: {identity}")
            seen_edges.add(identity)

        if openapi.get("openapi") != "3.1.0" or openapi.get("info", {}).get("version") != "1.0.0":
            fail("OpenAPI version metadata is invalid")
        paths = set(openapi.get("paths", {}))
        if paths != REQUIRED_PATHS:
            fail(f"OpenAPI path set differs from the approved read-only API: {sorted(paths)}")
        for path, item in openapi["paths"].items():
            disallowed = set(item) - {"get", "head", "options", "parameters", "summary", "description"}
            if disallowed:
                fail(f"OpenAPI exposes a non-read-only method at {path}: {sorted(disallowed)}")
        safety = openapi.get("x-codestra-safety", {})
        if safety != {
            "readOnly": True,
            "nativeApiProxy": False,
            "mutationProxy": False,
            "secretValueReadback": False,
            "runtimeActivationAuthorized": False,
        }:
            fail("OpenAPI safety declaration is invalid")

        dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
        if "ARG GO_BUILDER_IMAGE" not in dockerfile or "ARG RUNTIME_IMAGE" not in dockerfile:
            fail("Dockerfile must require builder and runtime image inputs")
        if re.search(r"^FROM\s+[^$].*:(?:latest|main|master)(?:\s|$)", dockerfile, re.MULTILINE | re.IGNORECASE):
            fail("Dockerfile contains a mutable image default")
        if "USER 65532:65532" not in dockerfile:
            fail("Dockerfile must run as a non-root identity")
        if "127.0.0.1:8090" not in dockerfile or "CODESTRA_CONTROL_API_AUTH_MODE=required" not in dockerfile:
            fail("Dockerfile must default to loopback and required authentication")

        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (CONTROL / "internal" / "controlapi").glob("*.go")
        )
        if 'http.MethodPost' not in source or 'StatusMethodNotAllowed' not in source:
            fail("server does not visibly enforce the read-only method boundary")
        if "io.LimitReader(response.Body, 4096)" not in source or "io.Discard" not in source:
            fail("upstream response bodies are not bounded and discarded")
        if "InsecureSkipVerify" in source:
            fail("TLS verification bypass is prohibited")
        if "CheckRedirect" not in source or "http.ErrUseLastResponse" not in source:
            fail("upstream redirects must be denied")

    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"CODESTRA_CONTROL_API=FAIL: {exc}", file=sys.stderr)
        return 1

    print("CODESTRA_CONTROL_API=PASS services=14 methods=GET,HEAD,OPTIONS native_proxy=false mutations=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
