# Backup, restore, and rollback

The control API is stateless. Before deployment, capture its current image digest, configuration checksums, Compose manifest, mounted secret-file paths without their values, and registry/OpenAPI files. Collector state and buffers must be handled under their own approved storage procedure.

Rollback uses the previous approved digest without rebuilding, preserves all volumes, renders Compose first, and performs a controlled `docker compose up -d`. Never use `docker compose down -v`.
