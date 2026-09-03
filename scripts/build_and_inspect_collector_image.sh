#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

manifest="codestra/release/image-build.v1.json"
builder="$(jq -r '.buildArgs.GO_BUILDER_IMAGE' "$manifest")"
upstream="$(jq -r '.buildArgs.OTELCOL_BASE_IMAGE' "$manifest")"
tag="local/codestra-opentelemetry:${source_sha}"
digest="sha256:$(printf '1%.0s' {1..64})"
identity="ghcr.io/appolon1908-hue/codestra-telemetry-opentelemetry@${digest}"
identity_environment=(
  --env "CODESTRA_SOURCE_SHA=$source_sha"
  --env "CODESTRA_IMAGE_DIGEST=$digest"
  --env "CODESTRA_OTELCOL_IMAGE=$identity"
  --env CODESTRA_BUSINESS=platform
  --env CODESTRA_OTLP_BIND_HOST=otel-collector-platform-ingress
  --env CODESTRA_METRICS_BIND_HOST=otel-collector-platform-metrics
)

container_id=""
copy_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/collector-image.XXXXXX")"
secret_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/collector-secrets.XXXXXX")"
cleanup() {
  if [[ -n "$container_id" ]]; then docker container rm -f "$container_id" >/dev/null; fi
  rm -rf -- "$copy_root"
  if [[ -d "$secret_root" ]]; then
    chmod 0700 "$secret_root"
    find "$secret_root" -type f -exec chmod 0600 {} \; -exec unlink {} \;
    rmdir "$secret_root"
  fi
}
trap cleanup EXIT
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj /CN=codestra-disposable-ca \
  -keyout "$secret_root/ca.key" -out "$secret_root/ca.crt" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes \
  -subj /CN=otel-collector-platform-ingress \
  -addext subjectAltName=IP:127.0.0.1,DNS:otel-collector-platform-ingress \
  -keyout "$secret_root/server.key" -out "$secret_root/server.csr" >/dev/null 2>&1
openssl x509 -req -days 1 -sha256 \
  -in "$secret_root/server.csr" -CA "$secret_root/ca.crt" -CAkey "$secret_root/ca.key" \
  -CAcreateserial -copy_extensions copy -out "$secret_root/server.crt" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes \
  -subj /CN=otel-collector \
  -addext subjectAltName=DNS:otel-collector \
  -keyout "$secret_root/legacy.key" -out "$secret_root/legacy.csr" >/dev/null 2>&1
openssl x509 -req -days 1 -sha256 \
  -in "$secret_root/legacy.csr" -CA "$secret_root/ca.crt" -CAkey "$secret_root/ca.key" \
  -CAcreateserial -copy_extensions copy -out "$secret_root/legacy.crt" >/dev/null 2>&1
chmod 0444 "$secret_root/ca.crt" "$secret_root/server.crt" "$secret_root/server.key" "$secret_root/legacy.crt"
chmod 0555 "$secret_root"
certificate_mounts=(
  --mount "type=bind,source=$secret_root/server.crt,target=/run/secrets/otelcol_server_cert,readonly"
  --mount "type=bind,source=$secret_root/server.key,target=/run/secrets/otelcol_server_key,readonly"
  --mount "type=bind,source=$secret_root/ca.crt,target=/run/secrets/otelcol_client_ca,readonly"
  --mount "type=bind,source=$secret_root/ca.crt,target=/run/secrets/otelcol_backend_ca,readonly"
)

docker build \
  --file codestra/deploy/Dockerfile \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "OTELCOL_BASE_IMAGE=$upstream" \
  --build-arg "CODESTRA_SOURCE_SHA=$source_sha" \
  --label "org.opencontainers.image.revision=$source_sha" \
  --tag "$tag" \
  .

docker run --rm "${identity_environment[@]}" "${certificate_mounts[@]}" "$tag" --version | grep -F '0.159.0'
docker image inspect "$tag" | jq -e \
  '.[0].Config.User == "10001:10001" and .[0].Config.Entrypoint == ["/codestra-otelcol-entrypoint"]'
test "$(docker image inspect "$tag" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$source_sha"
embedded_source="$(docker image inspect "$tag" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^CODESTRA_IMAGE_SOURCE_SHA=' || true)"
test "$embedded_source" = "CODESTRA_IMAGE_SOURCE_SHA=$source_sha"
if docker run --rm \
  --env "CODESTRA_SOURCE_SHA=$source_sha" \
  --env "CODESTRA_IMAGE_DIGEST=$digest" \
  --env "CODESTRA_OTELCOL_IMAGE=ghcr.io/example/collector@${digest}" \
  "$tag" --version >/dev/null 2>&1; then
  echo "Collector accepted an unauthorized runtime image identity" >&2
  exit 1
fi
if docker run --rm \
  "${identity_environment[@]}" \
  --mount "type=bind,source=$secret_root/legacy.crt,target=/run/secrets/otelcol_server_cert,readonly" \
  "$tag" --version >/dev/null 2>&1; then
  echo "Collector accepted a server certificate without the ingress DNS SAN" >&2
  exit 1
fi

docker run --rm \
  --add-host otel-collector-platform-ingress:127.0.0.1 \
  --add-host otel-collector-platform-metrics:127.0.0.1 \
  "${identity_environment[@]}" \
  "${certificate_mounts[@]}" \
  --env CODESTRA_ENVIRONMENT=test \
  --env CODESTRA_REGION=ci \
  --env CODESTRA_SERVER=github-actions \
  --env TEMPO_OTLP_GRPC_ENDPOINT=tempo:4317 \
  --env TEMPO_TLS_SERVER_NAME=temp.codestra.media \
  --env LOKI_OTLP_HTTP_ENDPOINT=https://loki:3100/otlp \
  --env LOKI_TLS_SERVER_NAME=loki.codestra.media \
  "$tag" validate --config=/etc/otelcol-contrib/config.yaml

container_id="$(docker run -d --network none --read-only \
  --add-host otel-collector-platform-ingress:127.0.0.1 \
  --add-host otel-collector-platform-metrics:127.0.0.1 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  --tmpfs /var/lib/otelcol/storage:rw,nosuid,nodev,uid=10001,gid=10001,mode=0700,size=64m \
  "${identity_environment[@]}" \
  --env CODESTRA_ENVIRONMENT=test \
  --env CODESTRA_REGION=ci \
  --env CODESTRA_SERVER=github-actions \
  --env TEMPO_OTLP_GRPC_ENDPOINT=tempo.invalid:4317 \
  --env TEMPO_TLS_SERVER_NAME=temp.codestra.media \
  --env LOKI_OTLP_HTTP_ENDPOINT=https://loki.invalid:3100/otlp \
  --env LOKI_TLS_SERVER_NAME=loki.codestra.media \
  "${certificate_mounts[@]}" \
  "$tag" --config=/etc/otelcol-contrib/config.yaml)"
for attempt in $(seq 1 45); do
  if docker exec "$container_id" /otelcol-healthcheck; then
    break
  fi
  if [[ "$attempt" -eq 45 ]]; then
    docker logs "$container_id"
    exit 1
  fi
  sleep 1
done
docker cp "$container_id:/etc/otelcol-contrib/config.yaml" "$copy_root/config.yaml"
docker cp "$container_id:/usr/share/codestra/image-build.v1.json" "$copy_root/image-build.v1.json"
docker cp "$container_id:/usr/share/codestra/runtime-base.lock.json" "$copy_root/runtime-base.lock.json"
docker cp "$container_id:/otelcol-healthcheck" "$copy_root/otelcol-healthcheck"
docker cp "$container_id:/usr/share/codestra/source-revision" "$copy_root/source-revision"
cmp codestra/collector.yaml "$copy_root/config.yaml"
cmp codestra/release/image-build.v1.json "$copy_root/image-build.v1.json"
cmp codestra/release/runtime-base.lock.json "$copy_root/runtime-base.lock.json"
test -x "$copy_root/otelcol-healthcheck"
test "$(cat "$copy_root/source-revision")" = "$source_sha"
echo "COLLECTOR_LOCKED_IMAGE_INSPECTION=PASS"
