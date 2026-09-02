# syntax=docker.io/docker/dockerfile@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG GO_BUILDER_IMAGE
ARG OTELCOL_BASE_IMAGE

FROM ${GO_BUILDER_IMAGE} AS healthcheck-builder
WORKDIR /src
COPY codestra/deploy/healthcheck.go ./healthcheck.go
COPY codestra/collector.yaml ./metadata/collector.yaml
COPY codestra/release/image-build.v1.json ./metadata/image-build.v1.json
COPY codestra/release/runtime-base.lock.json ./metadata/runtime-base.lock.json
RUN CGO_ENABLED=0 GOOS=linux go build \
      -buildvcs=false \
      -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/otelcol-healthcheck \
      ./healthcheck.go \
    && install -d -m 0755 /out/rootfs/var/lib/otelcol/storage \
    && install -d -m 0555 /out/rootfs/etc/otelcol-contrib /out/rootfs/usr/share/codestra \
    && install -m 0444 ./metadata/collector.yaml /out/rootfs/etc/otelcol-contrib/config.yaml \
    && install -m 0444 ./metadata/image-build.v1.json /out/rootfs/usr/share/codestra/image-build.v1.json \
    && install -m 0444 ./metadata/runtime-base.lock.json /out/rootfs/usr/share/codestra/runtime-base.lock.json

FROM ${OTELCOL_BASE_IMAGE}
LABEL org.opencontainers.image.title="Codestra Corporate OpenTelemetry Collector"
LABEL org.opencontainers.image.description="Business-isolated OTLP ingestion, redaction, tail sampling, durable queues and corporate telemetry normalization"
LABEL org.opencontainers.image.vendor="Codestra"
LABEL codestra.artifact.model="repository-configured-signed-image"

COPY --from=healthcheck-builder --chown=10001:10001 --chmod=0555 /out/otelcol-healthcheck /otelcol-healthcheck
COPY --from=healthcheck-builder --chown=10001:10001 /out/rootfs/ /

USER 10001:10001
