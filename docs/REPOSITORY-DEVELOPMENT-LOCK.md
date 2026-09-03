# Repository development lock

`REPOSITORY_DEVELOPMENT_LOCK.json` and
`deploy/evidence/CODESTRA-OBSERVABILITY-SOURCE-INVENTORY.json` form one
reviewed snapshot. They record source authority only and never enable a
runtime, deployment, public URL, or provider connection.

The exact-head workflow verifies each recorded revision against the protected `development` branch.
A successful push run from a feature branch cannot satisfy this evidence. For
every merged source PR, GitHub's comparison API must also prove that the
recorded merge is an ancestor of the locked development revision. The unsafe
public PostgreSQL Exporter proposal remains unmerged;
PostgreSQL Exporter PR #7 is verified independently by number, base branch,
head SHA, protected merge SHA, and ancestry before its private-only contract is
accepted.

The workflow token has read-only access to repository contents, Actions runs,
checks, commit statuses, and pull requests. No write scope, package publication,
or deployment permission is granted. This source-lock change does not publish
or deploy an image, so image release and installation manifests are not
applicable to this logical change.

## Updating the snapshot

Capture a new snapshot only after all source PRs intended for the lock have
reached protected development and their exact-head checks and review threads
are final. Update both JSON documents together, run the local structural tests,
then require the remote verifier on the exact PR head and synthetic merge.

## Rollback

Revert the protected merge that changed the lock and both evidence documents as
one unit. Re-run the exact-head structural and remote workflows. Never edit a
single locked SHA or reduce an expected run count to make a stale snapshot pass;
produce a newly reviewed complete snapshot instead. Rollback changes repository
evidence only and must not operate on a server or runtime.
