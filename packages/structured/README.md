<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# koinon structured

The structured-data domain for firefly koinon. It owns supported file readers, dataset tables, immutable snapshots, SQL execution and recorded source coordinates. The application backend supplies authentication, workspace permissions, canonical identities and the public API.

Install with `uv sync --extra dev --extra file-readers`. Run `uv run pytest tests/unit` for domain regression tests. Tests requiring PostgreSQL, Docker, external storage or a model provider retain their prerequisites; unit tests do not qualify those integrations.

Use the [product documentation](../../docs/index.md), [source-lineage guide](../../docs/guides/lineage.md) and [qualification record](../../docs/operations/qualification.md). The public Python, TypeScript and Java clients live in the root [SDK directory](../../sdk/README.md).

Historical implementation notes, migration identities and provenance records remain available for migration verification. They do not define the current public API or establish that every retained operation is admitted by the application.

Code is licensed under [Apache-2.0](LICENSE).
