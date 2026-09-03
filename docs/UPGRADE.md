# Upgrade policy

Update the control API source, digest-pinned Go builder, runtime image, runtime lock, and deterministic build manifest together on a feature branch. Exact-head CI must test the API and rebuild the locked image.

Update the Collector configuration, health probe, digest-pinned builder and upstream Collector image, runtime lock, and deterministic build manifest together on a feature branch. Exact-head CI must run the native configuration validator and rebuild and inspect the locked image. Do not move the repository-controlled `platform` identity into a runtime input.

Release each workload only from an exact protected production commit through the reusable signed-image authority. Promote the same immutable digest through test, staging, production, and main; repository readiness alone does not authorize activation.

The reusable Model A workflow always supplies `CODESTRA_SOURCE_SHA` from its
validated protected-production input. An image manifest may set
`embedSourceRevision: true`; that makes a matching Dockerfile
`ARG CODESTRA_SOURCE_SHA` and
`ENV CODESTRA_IMAGE_SOURCE_SHA=${CODESTRA_SOURCE_SHA}` mandatory. The release
workflow inspects that exact value in both the unpublished candidate and the
pulled published digest before signing. The value is derived by the release
workflow and must never be caller-authored in a build manifest.

Both runnable images validate that embedded source revision at process startup.
The Collector entrypoint and control API require it to equal the runtime source
SHA, and require the runtime digest to equal the canonical full image identity.
Any missing or conflicting value fails before the Collector handoff or API
configuration load.
The root build-context allowlist includes both Collector wrapper source and
test files; removing either entry makes the exact-head image build fail closed.
Release manifests are parsed with duplicate-key rejection so a later field
cannot silently override the reviewed source-embedding contract.
Exact-head image CI also starts both images without host networking, checks the
Collector metrics-network health extension, and checks both control API liveness and
readiness with a disposable mounted credential.

The Collector's business-ingress and observability interfaces use distinct,
repository-controlled aliases. OTLP receivers bind only to
`otel-collector-platform-ingress`; health and Prometheus endpoints bind only to
`otel-collector-platform-metrics`. Treat a change to either alias or to the
fixed `platform` business identity as an architecture change requiring the
same configuration, Compose, startup, and disposable-image gates.
