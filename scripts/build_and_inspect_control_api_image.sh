#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

manifest="codestra/control-api/release/image-build.v1.json"
builder="$(jq -r '.buildArgs.GO_BUILDER_IMAGE' "$manifest")"
runtime="$(jq -r '.buildArgs.RUNTIME_IMAGE' "$manifest")"
tag="local/codestra-control-api:${source_sha}"
digest="sha256:$(printf '2%.0s' {1..64})"
identity="ghcr.io/appolon1908-hue/codestra-telemetry-control-api@${digest}"
token_file="$(mktemp "${RUNNER_TEMP:-/tmp}/control-api-token.XXXXXX")"
openssl rand -hex 32 > "$token_file"
chmod 0444 "$token_file"

docker build \
  --file codestra/control-api/Dockerfile \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "RUNTIME_IMAGE=$runtime" \
  --build-arg "CODESTRA_SOURCE_SHA=$source_sha" \
  --label "org.opencontainers.image.revision=$source_sha" \
  --tag "$tag" \
  codestra/control-api

test "$(docker run --rm "$tag" --version)" = "codestra-observability-api repository-source"
docker image inspect "$tag" | jq -e \
  '.[0].Config.User == "65532:65532" and .[0].Config.Entrypoint == ["/usr/local/bin/codestra-observability-api"]'
test "$(docker image inspect "$tag" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$source_sha"
embedded_source="$(docker image inspect "$tag" \
  --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^CODESTRA_IMAGE_SOURCE_SHA=' || true)"
test "$embedded_source" = "CODESTRA_IMAGE_SOURCE_SHA=$source_sha"

if docker run --rm \
  --env "CODESTRA_SOURCE_SHA=$source_sha" \
  --env "CODESTRA_IMAGE_DIGEST=$digest" \
  --env "CODESTRA_CONTROL_API_IMAGE=ghcr.io/example/control-api@${digest}" \
  "$tag" >/dev/null 2>&1; then
  echo "control API accepted an unauthorized runtime image identity" >&2
  exit 1
fi

container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then docker container rm -f "$container_id" >/dev/null; fi
  if [[ -f "$token_file" ]]; then chmod 0600 "$token_file"; unlink "$token_file"; fi
}
trap cleanup EXIT
container_id="$(docker run -d --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --env "CODESTRA_SOURCE_SHA=$source_sha" \
  --env "CODESTRA_IMAGE_DIGEST=$digest" \
  --env "CODESTRA_CONTROL_API_IMAGE=$identity" \
  --env CODESTRA_CONTROL_API_BEARER_TOKEN_FILE=/run/secrets/control_api_bearer_token \
  --mount "type=bind,source=$token_file,target=/run/secrets/control_api_bearer_token,readonly" \
  "$tag")"
for attempt in $(seq 1 30); do
  if docker exec "$container_id" /usr/local/bin/codestra-control-api-healthcheck; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    docker logs "$container_id"
    exit 1
  fi
  sleep 1
done
copy_root="${RUNNER_TEMP:-/tmp}/control-api-image-${source_sha}"
mkdir -p "$copy_root"
docker cp "$container_id:/usr/share/codestra/image-build.v1.json" "$copy_root/image-build.v1.json"
docker cp "$container_id:/usr/share/codestra/runtime-base.lock.json" "$copy_root/runtime-base.lock.json"
docker cp "$container_id:/usr/share/codestra/source-revision" "$copy_root/source-revision"
cmp codestra/control-api/release/image-build.v1.json "$copy_root/image-build.v1.json"
cmp codestra/control-api/release/runtime-base.lock.json "$copy_root/runtime-base.lock.json"
test "$(cat "$copy_root/source-revision")" = "$source_sha"
echo "CONTROL_API_LOCKED_IMAGE_INSPECTION=PASS"
