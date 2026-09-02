#!/usr/bin/env bash
set -Eeuo pipefail

source_sha="${1:?exact source SHA is required}"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$source_sha"

manifest="codestra/control-api/release/image-build.v1.json"
builder="$(jq -r '.buildArgs.GO_BUILDER_IMAGE' "$manifest")"
runtime="$(jq -r '.buildArgs.RUNTIME_IMAGE' "$manifest")"
tag="local/codestra-control-api:${source_sha}"

docker build \
  --file codestra/control-api/Dockerfile \
  --build-arg "GO_BUILDER_IMAGE=$builder" \
  --build-arg "RUNTIME_IMAGE=$runtime" \
  --label "org.opencontainers.image.revision=$source_sha" \
  --tag "$tag" \
  codestra/control-api

test "$(docker run --rm "$tag" --version)" = "codestra-observability-api repository-source"
docker image inspect "$tag" | jq -e \
  '.[0].Config.User == "65532:65532" and .[0].Config.Entrypoint == ["/usr/local/bin/codestra-observability-api"]'
test "$(docker image inspect "$tag" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$source_sha"

container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then docker container rm "$container_id" >/dev/null; fi
}
trap cleanup EXIT
container_id="$(docker create "$tag")"
copy_root="${RUNNER_TEMP:-/tmp}/control-api-image-${source_sha}"
mkdir -p "$copy_root"
docker cp "$container_id:/usr/share/codestra/image-build.v1.json" "$copy_root/image-build.v1.json"
docker cp "$container_id:/usr/share/codestra/runtime-base.lock.json" "$copy_root/runtime-base.lock.json"
cmp codestra/control-api/release/image-build.v1.json "$copy_root/image-build.v1.json"
cmp codestra/control-api/release/runtime-base.lock.json "$copy_root/runtime-base.lock.json"
echo "CONTROL_API_LOCKED_IMAGE_INSPECTION=PASS"
