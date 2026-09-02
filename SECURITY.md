# Security policy

Report security issues privately to the repository owner. Never commit bearer tokens, certificates, private keys, collector credentials, upstream credentials, or production evidence containing secret values.

Secret scanning covers the complete repository. Its only exceptions are nine
exact paths for upstream Collector test-fixture keys, whose containing upstream
tree is immutably bound by `CODESTRA_UPSTREAM_LOCK.json`; no Codestra-owned path
or wildcard directory is excluded.

The observability control API is read-only, denies redirects and mutations, discards upstream bodies, requires bearer-token-file authentication by default, and has no public host binding in its deployment candidate.

The Collector accepts OTLP only through its private networks with mTLS secret files, overwrites caller identity with the repository-controlled `platform` identity, and exports through verified TLS. Its candidate is profile-disabled, deploy-only, non-root, read-only, capability-free, and has no published host ports.
