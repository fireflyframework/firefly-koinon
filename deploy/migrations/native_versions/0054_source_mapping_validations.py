# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Add bounded encrypted preparation without modifying accepted mapping evidence.

Transactional expansion: retry an interrupted transaction unchanged. Expired
transient data is removed only by fenced maintenance after payload cleanup.
Do not downgrade after use; repair with a new forward migration.
"""

from alembic import op

revision = "koinon_0054_mapping_validations"
down_revision = "koinon_0053_scheduler_state"


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Mapping validation requires PostgreSQL")
    op.execute("SET LOCAL lock_timeout='5s'")
    op.execute("""CREATE TABLE public.koinon_content_mapping_validations (
      id uuid PRIMARY KEY, tenant_id varchar(64) NOT NULL REFERENCES public.lattice_tenants(id),
      owner varchar(512) NOT NULL, operation_id uuid NOT NULL,
      session_hash varchar(64) NOT NULL, request_sha256 varchar(64) NOT NULL, request_ciphertext bytea,
      connection_id varchar(64) NOT NULL, connection_revision integer NOT NULL,
      authority_sha256 varchar(64) NOT NULL, mapping_id varchar(64), expected_revision integer,
      root_kind varchar(16) NOT NULL, root_proof_sha256 varchar(64) NOT NULL, root_proof_ciphertext bytea,
      walk_ciphertext bytea, checkpoint_ciphertext bytea,
      state varchar(32) NOT NULL DEFAULT 'scanning', revision integer NOT NULL DEFAULT 1,
      enumeration_complete boolean NOT NULL DEFAULT false,
      verification_position bigint NOT NULL DEFAULT 0, raw_observed_count bigint NOT NULL DEFAULT 0,
      eligible_count bigint NOT NULL DEFAULT 0, change_count bigint NOT NULL DEFAULT 0,
      scan_max_items integer NOT NULL, max_active_per_tenant integer NOT NULL DEFAULT 8,
      max_active_per_owner integer NOT NULL DEFAULT 2, max_records_per_tenant integer NOT NULL DEFAULT 1000,
      max_retained_bytes_per_tenant bigint NOT NULL DEFAULT 17179869184,
      reserved_bytes bigint NOT NULL, payload_bytes bigint NOT NULL DEFAULT 0,
      payload_released_at timestamptz, manifest_sha256 varchar(64),
      last_continuation_sha256 varchar(64), last_continuation_result_revision integer,
      reason_code varchar(64), cleanup_reason varchar(32), cleanup_position bigint NOT NULL DEFAULT 0,
      cleanup_claim_token uuid, cleanup_claim_until timestamptz, cleanup_last_attempt_at timestamptz,
      created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
      CONSTRAINT uq_content_validation_scope UNIQUE(tenant_id,id),
      CONSTRAINT uq_content_validation_operation UNIQUE(tenant_id,owner,operation_id),
      CONSTRAINT fk_content_validation_connection FOREIGN KEY(tenant_id,owner,connection_id)
        REFERENCES public.koinon_content_connections(tenant_id,owner,id),
      CONSTRAINT fk_content_validation_mapping FOREIGN KEY(tenant_id,owner,mapping_id)
        REFERENCES public.koinon_content_mappings(tenant_id,owner,id),
      CONSTRAINT ck_content_validation_mapping CHECK((mapping_id IS NULL)=(expected_revision IS NULL)),
      CONSTRAINT ck_content_validation_state CHECK(state IN
        ('scanning','verifying','checking_changes','complete','blocked','stale','cleaning','abandoned','expired')),
      CONSTRAINT ck_content_validation_root CHECK(root_kind IN ('file','folder')),
      CONSTRAINT ck_content_validation_revision CHECK(revision>0 AND connection_revision>0 AND expected_revision>0),
      CONSTRAINT ck_content_validation_counts CHECK(raw_observed_count>=0 AND eligible_count>=0
        AND change_count>=0 AND verification_position>=0 AND cleanup_position>=0),
      CONSTRAINT ck_content_validation_bounds CHECK(scan_max_items BETWEEN 100 AND 1000000
        AND max_active_per_tenant BETWEEN 1 AND 8 AND max_active_per_owner BETWEEN 1 AND 2
        AND max_active_per_owner<=max_active_per_tenant
        AND max_records_per_tenant BETWEEN max_active_per_tenant AND 1000
        AND max_retained_bytes_per_tenant BETWEEN scan_max_items::bigint*16384+8388608 AND 17179869184),
      CONSTRAINT ck_content_validation_expiry CHECK(expires_at>created_at AND expires_at<=created_at+interval '8 hours'),
      CONSTRAINT ck_content_validation_cleanup_claim CHECK((cleanup_claim_token IS NULL)=(cleanup_claim_until IS NULL)),
      CONSTRAINT ck_content_validation_continuation CHECK(
        (last_continuation_sha256 IS NULL)=(last_continuation_result_revision IS NULL)
        AND last_continuation_result_revision<=revision),
      CONSTRAINT ck_content_validation_bytes CHECK(payload_bytes BETWEEN 0 AND 8388608 AND reserved_bytes>=payload_bytes)
    )""")
    for name, columns, condition in (
        ("ix_content_validation_owner", "tenant_id,owner,created_at,id", ""),
        ("ix_content_validation_connection", "connection_id", ""),
        ("ix_content_validation_mapping", "mapping_id", ""),
        ("ix_content_validation_expiry", "expires_at,tenant_id,id", ""),
        (
            "ix_content_validation_cleanup",
            "cleanup_last_attempt_at NULLS FIRST,tenant_id,id",
            " WHERE state='cleaning'",
        ),
    ):
        op.execute(
            f"CREATE INDEX {name} ON public.koinon_content_mapping_validations({columns}){condition}"
        )
    op.execute("""CREATE TABLE public.koinon_content_mapping_validation_entries (
      tenant_id varchar(64) NOT NULL, validation_id uuid NOT NULL, item_id varchar(1024) NOT NULL,
      sequence bigint NOT NULL, parent_item_id varchar(1024), fingerprint_sha256 varchar(64) NOT NULL,
      candidate_ciphertext bytea NOT NULL, destination_key_sha256 varchar(64) NOT NULL,
      verified boolean NOT NULL DEFAULT false, payload_bytes bigint NOT NULL DEFAULT 0,
      PRIMARY KEY(tenant_id,validation_id,item_id),
      CONSTRAINT fk_content_validation_entry_scope FOREIGN KEY(tenant_id,validation_id)
        REFERENCES public.koinon_content_mapping_validations(tenant_id,id),
      CONSTRAINT uq_content_validation_sequence UNIQUE(tenant_id,validation_id,sequence),
      CONSTRAINT ck_content_validation_entry_sequence CHECK(sequence>=0),
      CONSTRAINT ck_content_validation_entry_bytes CHECK(payload_bytes BETWEEN 1 AND 16384)
    )""")
    op.execute("""CREATE INDEX ix_content_validation_destination ON
      public.koinon_content_mapping_validation_entries(tenant_id,validation_id,destination_key_sha256)""")
    from koinon.integrations.content_sources.mapping_validation_guards import statements

    for statement in statements():
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Retain preparation recovery identities; use a reviewed forward migration"
    )
