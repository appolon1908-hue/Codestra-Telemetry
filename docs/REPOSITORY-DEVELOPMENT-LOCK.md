# Repository development lock

`REPOSITORY_DEVELOPMENT_LOCK.json` and
`deploy/evidence/CODESTRA-OBSERVABILITY-SOURCE-INVENTORY.json` form one
reviewed source-authority evidence set. They never enable a runtime,
deployment, public URL, provider connection, business write, or production
activation.

The inventory records the immutable source pull-request evidence: repository,
PR, reviewed head, merge result, changed files, exact check names, conclusions,
and review-thread count. The lock records the protected `development` branch
revision that contains that source plus any later reviewed descendants.

The exact-head workflow verifies every locked revision against the live remote
branch. A successful feature-branch run cannot satisfy this evidence. For each
merged source PR, GitHub's comparison API must prove that the recorded merge is
an ancestor of the locked development revision. The unsafe public PostgreSQL
Exporter proposal remains unmerged; PostgreSQL Exporter PR #7 is verified
independently by number, base branch, head SHA, protected merge SHA, and
ancestry before its private-only contract is accepted.

The workflow token has read-only access to repository contents, Actions runs,
checks, commit statuses, and pull requests. No write scope, package
publication, or deployment permission is granted. This source-lock change does
not publish or deploy an image, so image release and installation manifests are
not applicable to this logical change.

## Updating the evidence set

When source-PR evidence changes, update both JSON documents together and review
the complete new snapshot.

When only a protected development branch advances through separately reviewed
and merged descendant PRs, refresh that repository's `developmentSha` and the
minimum successful protected-push count in
`REPOSITORY_DEVELOPMENT_LOCK.json`. Retain the immutable source-PR inventory;
the remote verifier must still prove source-merge ancestry, exact live branch
identity, successful protected push runs, unchanged source-PR evidence, and no
unresolved source review threads.

Never add a new runtime path to the verifier allowlist merely to make a stale
lock pass. Capture the exact protected revision instead. Any branch movement
after capture fails closed and requires another reviewed refresh.

## 2026-09-03 refresh

This refresh records the protected descendants that completed after the
original source inventory was captured:

- OpenTelemetry: `81552819fd16f8275b5711cd882347b605b3f5a3`
- Prometheus: `e45cf15cd71e5ade8e11e58771b6c480bb32a003`
- Alloy: `f4c4e6b19e6274578a97e1db0ca85e32339a2062`
- Superset: `d656a0eac2f8c335519e2ed3da2bd19046a54fbe`

Prometheus is captured after the protected merge of PR #41 corrected the
invalid workflow context that had produced a failed protected-push run. The
replacement SHA has two successful protected push workflows and no failed run.

The refresh does not approve a promotion. Its exact PR head must pass the local
structure tests, live remote verification, synthetic merge validation, and
independent review before it can merge.

## Rollback

Revert the protected merge that changed the lock and accompanying evidence as
one unit, then rerun the exact-head structural and remote workflows. Never edit
a locked SHA, suppress a failed remote comparison, or reduce an expected run
count merely to make stale evidence pass. Rollback changes repository evidence
only and must not operate on a server or runtime.
