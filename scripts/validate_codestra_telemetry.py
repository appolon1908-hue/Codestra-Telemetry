#!/usr/bin/env python3
"""Fail-closed validation for the Codestra OpenTelemetry Collector overlay."""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CODESTRA = ROOT / "codestra"
PROFILE = CODESTRA / "enterprise-profile.v1.json"
COLLECTOR = CODESTRA / "collector.yaml"
COMPOSE = CODESTRA / "compose.yaml"
DOCKERFILE = CODESTRA / "deploy" / "Dockerfile"
HEALTHCHECK = CODESTRA / "deploy" / "healthcheck.go"
ENV_EXAMPLE = CODESTRA / ".env.example"
FEATURES_DOC = CODESTRA / "docs" / "CORPORATE-FEATURES.md"
OPERATING_DOC = CODESTRA / "docs" / "OPERATING-MODEL.md"

BUSINESSES = {
    "platform",
    "codestra",
    "moneybee",
    "beyvra",
    "breero",
    "larim-a",
    "transportation",
    "booked4seasons",
    "social",
    "klyrow",
    "telnexa",
    "kyqra",
    "restaurant",
    "provisioning",
}
CANONICAL_RESOURCE_ATTRIBUTES = {
    "codestra.business",
    "codestra.application",
    "service.name",
    "service.version",
    "deployment.environment.name",
    "deployment.id",
    "cloud.region",
    "host.name",
}
CANONICAL_METRIC_LABELS = {
    "codestra_business",
    "application",
    "service",
    "service_version",
    "environment",
    "deployment",
    "region",
    "server",
    "tenant_scope",
}
REQUIRED_FEATURES = {
    "otlpGrpc",
    "otlpHttp",
    "mutualTlsIngress",
    "businessIdentityOverwrite",
    "requiredWorkloadIdentity",
    "canonicalMetricNormalization",
    "metricCardinalityProtection",
    "resourceAndAttributeRedaction",
    "tailSampling",
    "durableExporterQueues",
    "memoryBackpressure",
    "batching",
    "prometheusExport",
    "tempoExport",
    "lokiExport",
    "businessTenantHeaders",
    "healthEndpoint",
    "selfMetrics",
    "jsonSelfLogs",
    "immutablePackaging",
    "privateNetworks",
}
FORBIDDEN_IDENTITY_KEYS = {
    "tenant_id",
    "customer_id",
    "account_id",
    "user_id",
    "email",
    "phone",
    "request_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "message_id",
    "order_id",
    "workflow_id",
    "execution_id",
    "db.statement",
    "exception.message",
    "service.instance.id",
    "host.id",
    "container.id",
    "k8s.pod.uid",
    "process.pid",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")


def load_yaml(path: pathlib.Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid YAML {path.relative_to(ROOT)}: {exc}")


def require_file(path: pathlib.Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_profile() -> None:
    profile = load_json(PROFILE)
    if profile.get("schemaVersion") != "1.1":
        fail("enterprise profile schemaVersion must be 1.1")
    if profile.get("component") != "opentelemetry-collector":
        fail("enterprise profile component mismatch")
    if profile.get("canonicalHostname") != "otel.codestra.media":
        fail("canonical Collector hostname mismatch")
    if profile.get("exposure") != "internal_private":
        fail("Collector exposure must remain internal_private")
    if profile.get("status") != "CONFIG_PREPARED_NOT_DEPLOYED":
        fail("Collector status must remain CONFIG_PREPARED_NOT_DEPLOYED")
    if set(profile.get("businessScope", [])) != BUSINESSES:
        fail("enterprise profile must exactly represent the approved business catalogue")
    if set(profile.get("canonicalResourceAttributes", [])) != CANONICAL_RESOURCE_ATTRIBUTES:
        fail("profile resource attributes do not match the corporate contract")
    if set(profile.get("canonicalMetricLabels", [])) != CANONICAL_METRIC_LABELS:
        fail("profile metric labels do not match the Prometheus contract")
    if not FORBIDDEN_IDENTITY_KEYS.issubset(
        set(profile.get("forbiddenMetricLabelsOrResourceAttributes", []))
    ):
        fail("profile does not forbid all unsafe identity/cardinality fields")

    model = profile.get("instanceModel", {})
    if model.get("scope") != "one_approved_codestra_business_per_collector_instance":
        fail("Collector instance model must remain business-scoped")
    if model.get("callerSuppliedBusinessAttributeTrusted") is not False:
        fail("caller-supplied business identity may not be trusted")
    if model.get("crossBusinessIngestionDefault") != "deny":
        fail("cross-business ingestion must default to deny")

    disabled = sorted(
        name for name in REQUIRED_FEATURES
        if profile.get("features", {}).get(name) is not True
    )
    if disabled:
        fail(f"required corporate Collector features are disabled: {disabled}")
    if profile.get("sampling", {}).get("authority") != "opentelemetry-collector":
        fail("Collector must be the tail-sampling authority")
    if profile.get("sampling", {}).get("tempoPerformsAdditionalTailSampling") is not False:
        fail("Tempo may not claim a second tail-sampling authority")


def validate_collector() -> None:
    config = load_yaml(COLLECTOR)
    extensions = config.get("extensions", {})
    if set(extensions) != {"health_check", "file_storage"}:
        fail("Collector extensions must be health_check and file_storage")
    if extensions["file_storage"].get("directory") != "/var/lib/otelcol/storage":
        fail("file-backed exporter queues must use the durable Collector volume")

    receivers = config.get("receivers", {})
    if set(receivers) != {"otlp", "prometheus/internal"}:
        fail("Collector receivers must be governed OTLP plus internal self-scrape")
    protocols = receivers["otlp"].get("protocols", {})
    if set(protocols) != {"grpc", "http"}:
        fail("Collector must support OTLP/gRPC and OTLP/HTTP")
    for protocol, settings in protocols.items():
        tls = settings.get("tls", {})
        required = {
            "cert_file": "/run/secrets/otelcol_server_cert",
            "key_file": "/run/secrets/otelcol_server_key",
            "client_ca_file": "/run/secrets/otelcol_client_ca",
        }
        if tls != required:
            fail(f"OTLP/{protocol} must require the approved mutual-TLS files")

    processors = config.get("processors", {})
    required_processors = {
        "memory_limiter",
        "resource/codestra",
        "attributes/redact",
        "filter/required_identity",
        "filter/tenant_safe",
        "transform/metrics",
        "transform/traces",
        "transform/logs",
        "tail_sampling",
        "batch",
    }
    missing = required_processors - processors.keys()
    if missing:
        fail(f"Collector is missing required processors: {sorted(missing)}")

    resource_actions = processors["resource/codestra"].get("attributes", [])
    resource_by_key = {item.get("key"): item for item in resource_actions}
    business = resource_by_key.get("codestra.business", {})
    if business.get("action") != "upsert" or business.get("value") != "${env:CODESTRA_BUSINESS}":
        fail("Collector must overwrite business identity from deployment configuration")
    for key in ("deployment.environment.name", "cloud.region", "host.name"):
        if resource_by_key.get(key, {}).get("action") != "upsert":
            fail(f"Collector must overwrite trusted resource identity: {key}")
    for key in FORBIDDEN_IDENTITY_KEYS:
        dotted = key.replace("_", ".") if key in {"request_id", "correlation_id"} else key
        if key in resource_by_key and resource_by_key[key].get("action") != "delete":
            fail(f"unsafe resource action for {key}")
        if dotted in resource_by_key and resource_by_key[dotted].get("action") != "delete":
            fail(f"unsafe resource action for {dotted}")

    required_attributes = (
        "codestra.application",
        "service.name",
        "service.version",
        "deployment.id",
    )
    required_conditions = {
        condition
        for attribute in required_attributes
        for condition in (
            f'resource.attributes["{attribute}"] == nil',
            f'resource.attributes["{attribute}"] == ""',
        )
    }
    identity_filter = processors["filter/required_identity"]
    for signal in ("trace_conditions", "metric_conditions", "log_conditions"):
        if set(identity_filter.get(signal, [])) != required_conditions:
            fail(f"required-identity {signal} must reject missing and empty identity values")

    metric_transform = json.dumps(processors["transform/metrics"], sort_keys=True)
    for label in CANONICAL_METRIC_LABELS:
        if f'attributes[\\"{label}\\"]' not in metric_transform:
            fail(f"metric transform does not set canonical label {label}")
    for forbidden in (
        "tenant_id",
        "customer_id",
        "account_id",
        "user_id",
        "request_id",
        "trace_id",
        "message_id",
        "order_id",
        "db.statement",
        "container.id",
        "process.pid",
    ):
        if forbidden not in metric_transform:
            fail(f"metric transform does not remove {forbidden}")

    sampling = processors["tail_sampling"]
    if sampling.get("decision_wait") != "15s":
        fail("tail sampling decision_wait must be 15s")
    policies = {policy.get("name"): policy for policy in sampling.get("policies", [])}
    if set(policies) != {
        "preserve-errors",
        "preserve-high-latency",
        "preserve-critical-paths",
        "bounded-normal-success",
    }:
        fail("tail-sampling policy catalogue mismatch")
    if policies["preserve-errors"].get("type") != "status_code":
        fail("error traces must be preserved")
    if policies["preserve-high-latency"].get("latency", {}).get("threshold_ms") != 2000:
        fail("high-latency preservation threshold must remain 2000ms")
    if policies["bounded-normal-success"].get("probabilistic", {}).get("sampling_percentage") != 10:
        fail("routine successful trace sampling must remain 10% until calibrated")

    exporters = config.get("exporters", {})
    if set(exporters) != {"prometheus", "otlp/tempo", "otlphttp/loki"}:
        fail("Collector exporter catalogue mismatch")
    if exporters["prometheus"].get("resource_to_telemetry_conversion", {}).get("enabled") is not False:
        fail("Prometheus resource-to-label conversion must remain disabled")
    for name in ("otlp/tempo", "otlphttp/loki"):
        exporter = exporters[name]
        if exporter.get("headers", {}).get("X-Scope-OrgID") != "${env:CODESTRA_BUSINESS}":
            fail(f"{name} must receive the deployment-controlled business tenant")
        queue = exporter.get("sending_queue", {})
        if queue.get("enabled") is not True or queue.get("storage") != "file_storage":
            fail(f"{name} must use a file-backed sending queue")
        if queue.get("queue_size", 0) <= 0:
            fail(f"{name} queue_size must be positive")
        if exporter.get("retry_on_failure", {}).get("enabled") is not True:
            fail(f"{name} must retry bounded backend failures")
        expected_server_name = "${env:TEMPO_TLS_SERVER_NAME}" if name == "otlp/tempo" else "${env:LOKI_TLS_SERVER_NAME}"
        if exporter.get("tls") != {
            "insecure": False,
            "ca_file": "/run/secrets/otelcol_backend_ca",
            "server_name_override": expected_server_name,
        }:
            fail(f"{name} must verify the approved backend CA and service identity")

    service = config.get("service", {})
    if set(service.get("extensions", [])) != {"health_check", "file_storage"}:
        fail("service extension activation is incomplete")
    pipelines = service.get("pipelines", {})
    if set(pipelines) != {"metrics", "logs", "traces"}:
        fail("Collector must define metrics, logs and traces pipelines")
    if pipelines["metrics"].get("exporters") != ["prometheus"]:
        fail("Prometheus must remain the only metrics exporter")
    if pipelines["logs"].get("exporters") != ["otlphttp/loki"]:
        fail("Loki must remain the only logs exporter")
    if pipelines["traces"].get("exporters") != ["otlp/tempo"]:
        fail("Tempo must remain the only traces exporter")
    if "tail_sampling" not in pipelines["traces"].get("processors", []):
        fail("traces pipeline must activate tail sampling")
    telemetry = service.get("telemetry", {})
    if telemetry.get("logs", {}).get("encoding") != "json":
        fail("Collector self logs must be JSON")


def validate_runtime() -> None:
    compose = load_yaml(COMPOSE)
    service = compose.get("services", {}).get("otel-collector")
    if not service:
        fail("Compose candidate must define otel-collector")
    if service.get("user") != "10001:10001":
        fail("Collector must run as UID/GID 10001")
    if service.get("read_only") is not True:
        fail("Collector root filesystem must be read-only")
    if service.get("privileged") is True or service.get("network_mode") == "host":
        fail("Collector may not use privileged or host-network mode")
    if "ALL" not in service.get("cap_drop", []):
        fail("Collector must drop all Linux capabilities")
    if "no-new-privileges:true" not in service.get("security_opt", []):
        fail("Collector must set no-new-privileges")
    if service.get("ports"):
        fail("Collector may not publish host ports")
    if set(map(str, service.get("expose", []))) != {"4317", "4318", "8888", "8889", "13133"}:
        fail("Collector private port catalogue mismatch")
    if set(service.get("networks", [])) != {
        "codestra-business-telemetry",
        "codestra-observability",
    }:
        fail("Collector network boundary is incomplete")
    if set(service.get("secrets", [])) != {
        "otelcol_server_cert",
        "otelcol_server_key",
        "otelcol_client_ca",
        "otelcol_backend_ca",
    }:
        fail("Collector TLS secret-file contract is incomplete")
    if "otelcol-storage:/var/lib/otelcol" not in [str(item) for item in service.get("volumes", [])]:
        fail("Collector durable queue volume is missing")
    if any("/etc/otelcol-contrib/config.yaml" in str(item) for item in service.get("volumes", [])):
        fail("Collector runtime must use the immutable configuration embedded in the image")
    storage = compose.get("volumes", {}).get("otelcol-storage", {})
    if storage.get("external") is not True:
        fail("Collector durable queue volume must be externally lifecycle-managed")
    storage_name = str(storage.get("name", ""))
    if "${CODESTRA_BUSINESS:" not in storage_name or not storage_name.endswith("-otelcol-storage"):
        fail("Collector durable queue volume must be scoped by the approved business identity")
    if service.get("healthcheck", {}).get("test") != ["CMD", "/otelcol-healthcheck"]:
        fail("Collector must use the native health probe")

    image = str(service.get("image", ""))
    if "${CODESTRA_OTELCOL_IMAGE:" not in image or "sha256" not in image:
        fail("Collector final image must require an immutable digest")
    build_args = service.get("build", {}).get("args", {})
    if set(build_args) != {"GO_BUILDER_IMAGE", "OTELCOL_BASE_IMAGE"}:
        fail("Collector build must pin builder and upstream images")
    limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
    for field in ("cpus", "memory", "pids"):
        if field not in limits:
            fail(f"Collector runtime is missing resource limit {field}")

    serialized = COMPOSE.read_text(encoding="utf-8")
    for forbidden in (
        ":latest",
        "privileged: true",
        "network_mode: host",
        "/var/run/docker.sock",
        "0.0.0.0:4317",
        "0.0.0.0:4318",
    ):
        if forbidden in serialized:
            fail(f"Collector runtime contains forbidden content: {forbidden}")

    dockerfile = require_file(DOCKERFILE)
    for fragment in (
        "ARG GO_BUILDER_IMAGE",
        "ARG OTELCOL_BASE_IMAGE",
        "CGO_ENABLED=0",
        "-trimpath",
        "/otelcol-healthcheck",
        "/etc/otelcol-contrib/config.yaml",
        "USER 10001:10001",
    ):
        if fragment not in dockerfile:
            fail(f"Collector Dockerfile is missing {fragment}")
    healthcheck = require_file(HEALTHCHECK)
    if "http://127.0.0.1:13133/" not in healthcheck:
        fail("Collector health probe must use the local health extension")
    if "os/exec" in healthcheck or "exec.Command" in healthcheck:
        fail("Collector health probe may not invoke a shell or subprocess")


def validate_docs_and_source_safety() -> None:
    require_file(ENV_EXAMPLE)
    require_file(FEATURES_DOC)
    require_file(OPERATING_DOC)

    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for required in (
        "CODESTRA_BUSINESS=platform",
        "CODESTRA_BUSINESS_TELEMETRY_NETWORK=",
        "GO_BUILDER_IMAGE=",
        "OTELCOL_BASE_IMAGE=",
        "CODESTRA_OTELCOL_IMAGE=",
        "OTELCOL_SERVER_CERT_SECRET_NAME=",
        "OTELCOL_SERVER_KEY_SECRET_NAME=",
        "OTELCOL_CLIENT_CA_SECRET_NAME=",
        "OTELCOL_BACKEND_CA_SECRET_NAME=",
        "TEMPO_TLS_SERVER_NAME=",
        "LOKI_TLS_SERVER_NAME=",
    ):
        if required not in env_text:
            fail(f"runtime example omits {required}")

    dash = chr(45) * 5
    signatures = (
        dash + "BEGIN " + "PRIVATE" + chr(32) + "KEY" + dash,
        dash + "BEGIN " + "OPENSSH" + chr(32) + "PRIVATE" + chr(32) + "KEY" + dash,
        "A" + "K" + "I" + "A",
    )
    for path in CODESTRA.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for signature in signatures:
            if signature in text:
                fail(f"secret-shaped material found in {path.relative_to(ROOT)}")

    collector_text = COLLECTOR.read_text(encoding="utf-8").lower()
    for pattern in (
        r"(?m)^\s*password\s*:",
        r"(?m)^\s*client_secret\s*:",
        r"(?m)^\s*access_token\s*:",
        r"(?m)^\s*authorization\s*:",
    ):
        if re.search(pattern, collector_text):
            fail("Collector source contains an inline credential field")


def main() -> None:
    validate_profile()
    validate_collector()
    validate_runtime()
    validate_docs_and_source_safety()
    print("Codestra OpenTelemetry corporate configuration validation PASS")


if __name__ == "__main__":
    main()
