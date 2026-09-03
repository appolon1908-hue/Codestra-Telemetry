# syntax=docker.io/docker/dockerfile@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG GO_BUILDER_IMAGE
ARG RUNTIME_IMAGE
ARG CODESTRA_SOURCE_SHA

FROM ${GO_BUILDER_IMAGE} AS build
ARG CODESTRA_SOURCE_SHA
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 GOOS=linux go test ./... \
    && CGO_ENABLED=0 GOOS=linux go build -buildvcs=false -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/codestra-observability-api ./cmd/codestra-observability-api \
    && CGO_ENABLED=0 GOOS=linux go build -buildvcs=false -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/codestra-control-api-healthcheck ./cmd/healthcheck
COPY config/services.json ./metadata/services.json
COPY openapi.json ./metadata/openapi.json
COPY release/image-build.v1.json ./metadata/image-build.v1.json
COPY release/runtime-base.lock.json ./metadata/runtime-base.lock.json
RUN install -d -m 0555 /out/rootfs/etc/codestra-observability /out/rootfs/usr/share/codestra \
    && install -m 0444 ./metadata/services.json /out/rootfs/etc/codestra-observability/services.json \
    && install -m 0444 ./metadata/openapi.json /out/rootfs/etc/codestra-observability/openapi.json \
    && install -m 0444 ./metadata/image-build.v1.json /out/rootfs/usr/share/codestra/image-build.v1.json \
    && install -m 0444 ./metadata/runtime-base.lock.json /out/rootfs/usr/share/codestra/runtime-base.lock.json
RUN test "${#CODESTRA_SOURCE_SHA}" -eq 40 \
    && printf '%s\n' "$CODESTRA_SOURCE_SHA" > /out/rootfs/usr/share/codestra/source-revision \
    && chmod 0444 /out/rootfs/usr/share/codestra/source-revision

FROM ${RUNTIME_IMAGE}
ARG CODESTRA_SOURCE_SHA
LABEL org.opencontainers.image.title="Codestra Observability Control API"
LABEL org.opencontainers.image.description="Private authenticated read-only control plane for fourteen Codestra observability authorities"
LABEL org.opencontainers.image.vendor="Codestra"
LABEL codestra.artifact.model="repository-built-signed-image"

COPY --from=build --chown=65532:65532 --chmod=0555 /out/codestra-observability-api /usr/local/bin/codestra-observability-api
COPY --from=build --chown=65532:65532 --chmod=0555 /out/codestra-control-api-healthcheck /usr/local/bin/codestra-control-api-healthcheck
COPY --from=build --chown=65532:65532 /out/rootfs/ /
USER 65532:65532
ENV CODESTRA_IMAGE_SOURCE_SHA=${CODESTRA_SOURCE_SHA}
ENV CODESTRA_CONTROL_API_REGISTRY_FILE=/etc/codestra-observability/services.json \
    CODESTRA_CONTROL_API_OPENAPI_FILE=/etc/codestra-observability/openapi.json \
    CODESTRA_CONTROL_API_LISTEN_ADDRESS=127.0.0.1:8090 \
    CODESTRA_CONTROL_API_AUTH_MODE=required
ENTRYPOINT ["/usr/local/bin/codestra-observability-api"]
