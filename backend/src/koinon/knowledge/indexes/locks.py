# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native data-source scoped writer/switch coordination without process-global locks."""


def lock_key(domain, tenant_id, workspace_id):
    if domain == "canon":
        from flycanon.core.services.embeddings.embedding_sets import index_lock_key
    else:
        from flyquery.core.services.retrieval.index_scope import index_lock_key
    return index_lock_key(tenant_id, workspace_id)
