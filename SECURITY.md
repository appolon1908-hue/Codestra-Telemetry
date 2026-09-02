# Security policy

Report security issues privately to the repository owner. Never commit bearer tokens, certificates, private keys, collector credentials, upstream credentials, or production evidence containing secret values.

The observability control API is read-only, denies redirects and mutations, discards upstream bodies, requires bearer-token-file authentication by default, and has no public host binding in its deployment candidate.
