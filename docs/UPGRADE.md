# Upgrade policy

Update the control API source, digest-pinned Go builder, runtime image, runtime lock, and deterministic build manifest together on a feature branch. Exact-head CI must test the API and rebuild the locked image.

Update the Collector configuration, health probe, digest-pinned builder and upstream Collector image, runtime lock, and deterministic build manifest together on a feature branch. Exact-head CI must run the native configuration validator and rebuild and inspect the locked image. Do not move the repository-controlled `platform` identity into a runtime input.

Release each workload only from an exact protected production commit through the reusable signed-image authority. Promote the same immutable digest through test, staging, production, and main; repository readiness alone does not authorize activation.
