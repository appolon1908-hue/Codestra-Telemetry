#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

manifest="codestra/release/image-build.v1.json"
builder="$(jq -r '.buildArgs.GO_BUILDER_IMAGE' "$manifest")"
upstream="$(jq -r '.buildArgs.OTELCOL_BASE_IMAGE' "$manifest")"
tag="local/codestra-opentelemetry:${source_sha}"

docker build \
  --file codestra/deploy/Dockerfile \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "OTELCOL_BASE_IMAGE=$upstream" \
  --build-arg "CODESTRA_SOURCE_SHA=$source_sha" \
  --label "org.opencontainers.image.revision=$source_sha" \
  --tag "$tag" \
  .

docker run --rm "$tag" --version | grep -F '0.159.0'
docker image inspect "$tag" | jq -e \
  '.[0].Config.User == "10001:10001" and .[0].Config.Entrypoint == ["/otelcol-contrib"]'
test "$(docker image inspect "$tag" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$source_sha"
embedded_source="$(docker image inspect "$tag" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^CODESTRA_IMAGE_SOURCE_SHA=' || true)"
test "$embedded_source" = "CODESTRA_IMAGE_SOURCE_SHA=$source_sha"

docker run --rm \
  --env CODESTRA_BUSINESS=platform \
  --env CODESTRA_ENVIRONMENT=test \
  --env CODESTRA_REGION=ci \
  --env CODESTRA_SERVER=github-actions \
  --env TEMPO_OTLP_GRPC_ENDPOINT=tempo:4317 \
  --env TEMPO_TLS_SERVER_NAME=temp.codestra.media \
  --env LOKI_OTLP_HTTP_ENDPOINT=https://loki:3100/otlp \
  --env LOKI_TLS_SERVER_NAME=loki.codestra.media \
  "$tag" validate --config=/etc/otelcol-contrib/config.yaml

container_id=""
copy_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/collector-image.XXXXXX")"
cleanup() {
  if [[ -n "$container_id" ]]; then docker container rm "$container_id" >/dev/null; fi
  rm -rf -- "$copy_root"
}
trap cleanup EXIT
container_id="$(docker create "$tag")"
docker cp "$container_id:/etc/otelcol-contrib/config.yaml" "$copy_root/config.yaml"
docker cp "$container_id:/usr/share/codestra/image-build.v1.json" "$copy_root/image-build.v1.json"
docker cp "$container_id:/usr/share/codestra/runtime-base.lock.json" "$copy_root/runtime-base.lock.json"
docker cp "$container_id:/otelcol-healthcheck" "$copy_root/otelcol-healthcheck"
cmp codestra/collector.yaml "$copy_root/config.yaml"
cmp codestra/release/image-build.v1.json "$copy_root/image-build.v1.json"
cmp codestra/release/runtime-base.lock.json "$copy_root/runtime-base.lock.json"
test -x "$copy_root/otelcol-healthcheck"
echo "COLLECTOR_LOCKED_IMAGE_INSPECTION=PASS"
