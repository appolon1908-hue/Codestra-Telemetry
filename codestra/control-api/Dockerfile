ARG GO_BUILDER_IMAGE
FROM ${GO_BUILDER_IMAGE} AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 GOOS=linux go test ./... \
    && CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags='-s -w' \
      -o /out/codestra-observability-api ./cmd/codestra-observability-api

ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}
COPY --from=build /out/codestra-observability-api /usr/local/bin/codestra-observability-api
COPY config/services.json /etc/codestra-observability/services.json
COPY openapi.json /etc/codestra-observability/openapi.json
USER 65532:65532
ENV CODESTRA_CONTROL_API_REGISTRY_FILE=/etc/codestra-observability/services.json \
    CODESTRA_CONTROL_API_OPENAPI_FILE=/etc/codestra-observability/openapi.json \
    CODESTRA_CONTROL_API_LISTEN_ADDRESS=127.0.0.1:8090 \
    CODESTRA_CONTROL_API_AUTH_MODE=required
ENTRYPOINT ["/usr/local/bin/codestra-observability-api"]
