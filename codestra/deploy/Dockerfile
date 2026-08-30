# syntax=docker/dockerfile:1.7

ARG GO_BUILDER_IMAGE
ARG OTELCOL_BASE_IMAGE

FROM ${GO_BUILDER_IMAGE} AS healthcheck-builder
WORKDIR /src
COPY codestra/deploy/healthcheck.go ./healthcheck.go
RUN CGO_ENABLED=0 GOOS=linux go build \
      -trimpath \
      -ldflags='-s -w -buildid=' \
      -o /out/otelcol-healthcheck \
      ./healthcheck.go \
    && mkdir -p /out/otelcol-storage/storage

FROM ${OTELCOL_BASE_IMAGE}
LABEL org.opencontainers.image.title="Codestra Corporate OpenTelemetry Collector"
LABEL org.opencontainers.image.description="Business-isolated OTLP ingestion, redaction, tail sampling, durable queues and corporate telemetry normalization"
LABEL org.opencontainers.image.vendor="Codestra"

COPY --from=healthcheck-builder --chown=10001:10001 --chmod=0555 /out/otelcol-healthcheck /otelcol-healthcheck
COPY --from=healthcheck-builder --chown=10001:10001 /out/otelcol-storage /var/lib/otelcol
COPY --chown=10001:10001 --chmod=0444 codestra/collector.yaml /etc/otelcol-contrib/config.yaml

USER 10001:10001