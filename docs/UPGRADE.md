# Upgrade policy

Update the control API source, digest-pinned Go builder, runtime image, runtime lock, and deterministic build manifest together on a feature branch. Exact-head CI must test the API and rebuild the locked image.

Release only an exact protected production commit through the reusable signed-image authority. Promote the same immutable digest through test, staging, production, and main; repository readiness alone does not authorize activation.
