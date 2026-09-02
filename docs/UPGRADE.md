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
