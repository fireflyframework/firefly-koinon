# firefly koinon storage

Independent bounded Azure Blob Storage and Google Cloud Storage byte transport shared by the native document, structured and private attachment ports. Clients and workload credentials are lazy; configuration does not contact providers. Existing containers/buckets are required.

Install optional `azure` or `gcs` extras. See the product [storage guide](../../docs/operations/storage.md) for deployment profiles, immutable-key semantics, limits and cloud acceptance boundaries.

Run `uv sync --extra dev --extra azure --extra gcs`, `uv run pytest`, `uv run ruff check src tests` and `uv run pyright` in this package. Actual SDK HTTP tests use fixture-owned loopback endpoints. Native Parquet executor cases additionally run with the backend environment, which provides the native structured package and PyArrow.

Copyright 2026 Firefly Software Foundation. Apache-2.0. Made with <3.
