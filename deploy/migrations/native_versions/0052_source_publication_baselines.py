# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retain original canonical reservations and immutable publication acknowledgements.

Additive, transactional expansion with a bounded lock wait. No historical evidence
is invented. An interrupted transaction rolls back and can be retried. Once in use,
retain evidence and repair through a reviewed forward migration; do not downgrade
to a writer that acknowledges source publications without these guards.
"""

from alembic import op

revision = "koinon_0052_publication_baseline"
down_revision = "koinon_0051_audit_provenance"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Source publication baselines require PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("ALTER TABLE public.koinon_catalog_history_identities ADD COLUMN creation_transaction xid8")
    op.execute("""CREATE TABLE public.koinon_content_publication_baselines (
        attempt_id varchar(64) PRIMARY KEY REFERENCES public.koinon_content_imports(id),
        tenant_id varchar(64) NOT NULL REFERENCES public.lattice_tenants(id),
        workspace_id varchar(64) NOT NULL, project_id varchar(64) NOT NULL,
        mapping_id varchar(64) NOT NULL REFERENCES public.koinon_content_mappings(id),
        object_id varchar(64) NOT NULL REFERENCES public.koinon_content_objects(id),
        source_id varchar(64) NOT NULL, asset_id varchar(64) NOT NULL,
        producer_kind varchar(32) NOT NULL CONSTRAINT ck_content_publication_producer
          CHECK(producer_kind IN ('initial_document','initial_dataset','replace_document','replace_dataset')),
        previous_attempt_id varchar(64) REFERENCES public.koinon_content_publication_baselines(attempt_id),
        descriptor_json jsonb, descriptor_sha256 varchar(64),
        acknowledgement_json jsonb, acknowledgement_sha256 varchar(64), created_at timestamptz NOT NULL,
        CONSTRAINT uq_content_publication_scope UNIQUE(attempt_id,tenant_id)
    )""")
    op.execute(
        "CREATE INDEX ix_content_publication_object ON "
        "public.koinon_content_publication_baselines(tenant_id,object_id,attempt_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_publication_previous ON "
        "public.koinon_content_publication_baselines(previous_attempt_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_publication_mapping ON "
        "public.koinon_content_publication_baselines(mapping_id)"
    )
    op.execute(
        "CREATE INDEX ix_content_publication_object_fk ON "
        "public.koinon_content_publication_baselines(object_id)"
    )
    op.execute("""CREATE TABLE public.koinon_content_publication_targets (
        attempt_id varchar(64) NOT NULL, catalog_id varchar(64) NOT NULL,
        tenant_id varchar(64) NOT NULL, workspace_id varchar(64) NOT NULL, project_id varchar(64) NOT NULL,
        role varchar(16) NOT NULL CONSTRAINT ck_content_publication_role
          CHECK(role IN ('source','asset','old_index','new_index','member')),
        disposition varchar(16) NOT NULL CONSTRAINT ck_content_publication_disposition
          CHECK(disposition IN ('retain','add','remove')),
        parent_id varchar(64), kind varchar(32) NOT NULL,
        mutation_revision bigint NOT NULL CONSTRAINT ck_content_publication_revision
          CHECK(mutation_revision>0),
        status varchar(32) NOT NULL, native_domain varchar(32), native_workspace_id varchar(64),
        native_id varchar(64), native_version_id varchar(64), native_snapshot_id varchar(64),
        PRIMARY KEY(attempt_id,catalog_id),
        CONSTRAINT fk_content_publication_target_scope FOREIGN KEY(attempt_id,tenant_id)
          REFERENCES public.koinon_content_publication_baselines(attempt_id,tenant_id)
    )""")
    op.execute("""CREATE TABLE public.koinon_content_publication_transactions (
        attempt_id varchar(64) PRIMARY KEY REFERENCES public.koinon_content_publication_baselines(attempt_id),
        transaction_id xid8 NOT NULL, native_receipt jsonb NOT NULL,
        write_counts jsonb NOT NULL, closed boolean NOT NULL
    )""")
    op.execute(
        "CREATE INDEX ix_content_publication_transaction ON "
        "public.koinon_content_publication_transactions(transaction_id,attempt_id)"
    )
    from koinon.integrations.content_sources.publication_guards import statements

    for statement in statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Retain publication evidence; use a reviewed forward migration")
