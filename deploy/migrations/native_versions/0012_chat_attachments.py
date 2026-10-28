# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private owner/thread file metadata, lexical evidence and immutable run links."""

from alembic import op

revision = "koinon_0012_chat_attachments"
down_revision = "koinon_0011_corporate_identity"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE public.koinon_chat_attachments (
    id VARCHAR(64) NOT NULL, 
    tenant_id VARCHAR(64) NOT NULL, 
    subject VARCHAR(512) NOT NULL, 
    thread_id VARCHAR(64) NOT NULL, 
    request_key VARCHAR(64) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    declared_media_type VARCHAR(128), 
    media_type VARCHAR(128) NOT NULL, 
    kind VARCHAR(16) NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    revision INTEGER NOT NULL, 
    job_id VARCHAR(64), 
    expiry_job_id VARCHAR(64), 
    access_token_id VARCHAR(64), 
    page_count INTEGER, 
    chunk_count INTEGER NOT NULL, 
    text_char_count INTEGER NOT NULL, 
    normalized_sha256 VARCHAR(64), 
    normalized_media_type VARCHAR(128), 
    normalized_size_bytes INTEGER, 
    image_width INTEGER, 
    image_height INTEGER, 
    warnings JSON NOT NULL, 
    error_code VARCHAR(64), 
    error VARCHAR(500), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_chat_attachment_request UNIQUE (tenant_id, subject, thread_id, request_key), 
    CONSTRAINT ck_chat_attachment_size CHECK (size_bytes > 0), 
    CONSTRAINT ck_chat_attachment_revision CHECK (revision > 0), 
    CONSTRAINT ck_chat_attachment_kind CHECK (kind in ('document','image','bundle')), 
    FOREIGN KEY(tenant_id) REFERENCES public.lattice_tenants (id), 
    FOREIGN KEY(thread_id) REFERENCES public.koinon_chat_threads (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_chat_attachment_expiry ON public.koinon_chat_attachments (expires_at, status)""",
    """CREATE INDEX ix_chat_attachment_owner ON public.koinon_chat_attachments (tenant_id, subject, thread_id, created_at, id)""",
    """CREATE TABLE public.koinon_chat_attachment_chunks (
    id VARCHAR(64) NOT NULL, 
    attachment_id VARCHAR(64) NOT NULL, 
    tenant_id VARCHAR(64) NOT NULL, 
    subject VARCHAR(512) NOT NULL, 
    thread_id VARCHAR(64) NOT NULL, 
    ordinal INTEGER NOT NULL, 
    text VARCHAR NOT NULL, 
    page INTEGER, 
    section_path JSON NOT NULL, 
    char_start INTEGER NOT NULL, 
    char_end INTEGER NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_chat_attachment_chunk_order UNIQUE (attachment_id, ordinal), 
    CONSTRAINT ck_chat_attachment_offsets CHECK (char_start >= 0 AND char_end >= char_start), 
    FOREIGN KEY(attachment_id) REFERENCES public.koinon_chat_attachments (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_chat_attachment_chunk_owner ON public.koinon_chat_attachment_chunks (tenant_id, subject, thread_id, attachment_id)""",
    """CREATE TABLE public.koinon_chat_attachment_links (
    run_id VARCHAR(64) NOT NULL, 
    attachment_id VARCHAR(64) NOT NULL, 
    message_id VARCHAR(64) NOT NULL, 
    tenant_id VARCHAR(64) NOT NULL, 
    subject VARCHAR(512) NOT NULL, 
    thread_id VARCHAR(64) NOT NULL, 
    ordinal INTEGER NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    revision INTEGER NOT NULL, 
    snapshot JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (run_id, attachment_id), 
    CONSTRAINT uq_chat_attachment_link_order UNIQUE (run_id, ordinal), 
    FOREIGN KEY(run_id) REFERENCES public.koinon_chat_runs (id) ON DELETE CASCADE, 
    FOREIGN KEY(attachment_id) REFERENCES public.koinon_chat_attachments (id), 
    FOREIGN KEY(message_id) REFERENCES public.koinon_chat_messages (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_chat_attachment_link_message ON public.koinon_chat_attachment_links (tenant_id, subject, thread_id, message_id)""",
    """CREATE TABLE public.koinon_chat_attachment_promotions (
    id VARCHAR(64) NOT NULL, 
    attachment_id VARCHAR(64) NOT NULL, 
    tenant_id VARCHAR(64) NOT NULL, 
    subject VARCHAR(512) NOT NULL, 
    thread_id VARCHAR(64) NOT NULL, 
    request_key VARCHAR(64) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    action VARCHAR(32) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    revision INTEGER NOT NULL, 
    values_json JSON NOT NULL, 
    source_catalog_id VARCHAR(64), 
    content_version_id VARCHAR(64), 
    result_json JSON, 
    error_code VARCHAR(64), 
    error VARCHAR(500), 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_chat_attachment_promotion UNIQUE (tenant_id, subject, thread_id, request_key), 
    CONSTRAINT ck_chat_attachment_action CHECK (action in ('add','replace_document','replace_table')), 
    FOREIGN KEY(attachment_id) REFERENCES public.koinon_chat_attachments (id), 
    FOREIGN KEY(source_catalog_id) REFERENCES public.lattice_catalog (id), 
    FOREIGN KEY(content_version_id) REFERENCES public.lattice_catalog (id)
)""",
    """CREATE INDEX ix_chat_attachment_promotion_owner ON public.koinon_chat_attachment_promotions (tenant_id, subject, thread_id, attachment_id)""",
    """CREATE INDEX ix_chat_attachment_chunk_search ON public.koinon_chat_attachment_chunks USING gin(to_tsvector('simple'::regconfig,text))""",
    """ALTER TABLE public.koinon_chat_attachments ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE public.koinon_chat_attachments FORCE ROW LEVEL SECURITY""",
    """CREATE POLICY owner_thread_scope ON public.koinon_chat_attachments
USING (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachments.thread_id
    AND t.tenant_id=koinon_chat_attachments.tenant_id
    AND t.subject=koinon_chat_attachments.subject))
WITH CHECK (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachments.thread_id
    AND t.tenant_id=koinon_chat_attachments.tenant_id
    AND t.subject=koinon_chat_attachments.subject))""",
    """REVOKE ALL ON public.koinon_chat_attachments FROM PUBLIC""",
    """ALTER TABLE public.koinon_chat_attachment_chunks ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE public.koinon_chat_attachment_chunks FORCE ROW LEVEL SECURITY""",
    """CREATE POLICY owner_thread_scope ON public.koinon_chat_attachment_chunks
USING (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_chunks.thread_id
    AND t.tenant_id=koinon_chat_attachment_chunks.tenant_id
    AND t.subject=koinon_chat_attachment_chunks.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_chunks.attachment_id
    AND a.tenant_id=koinon_chat_attachment_chunks.tenant_id
    AND a.subject=koinon_chat_attachment_chunks.subject
    AND a.thread_id=koinon_chat_attachment_chunks.thread_id
    AND ((a.expires_at>clock_timestamp()
    AND a.status IN ('extracting','ready'))
        OR (current_setting('app.attachment_purpose',true)='purge'
    AND (a.expires_at<=clock_timestamp()
        OR a.status='deleted')))))
WITH CHECK (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_chunks.thread_id
    AND t.tenant_id=koinon_chat_attachment_chunks.tenant_id
    AND t.subject=koinon_chat_attachment_chunks.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_chunks.attachment_id
    AND a.tenant_id=koinon_chat_attachment_chunks.tenant_id
    AND a.subject=koinon_chat_attachment_chunks.subject
    AND a.thread_id=koinon_chat_attachment_chunks.thread_id
    AND ((a.expires_at>clock_timestamp()
    AND a.status IN ('extracting','ready'))
        OR (current_setting('app.attachment_purpose',true)='purge'
    AND (a.expires_at<=clock_timestamp()
        OR a.status='deleted')))))""",
    """REVOKE ALL ON public.koinon_chat_attachment_chunks FROM PUBLIC""",
    """ALTER TABLE public.koinon_chat_attachment_links ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE public.koinon_chat_attachment_links FORCE ROW LEVEL SECURITY""",
    """CREATE POLICY owner_thread_scope ON public.koinon_chat_attachment_links
USING (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_links.thread_id
    AND t.tenant_id=koinon_chat_attachment_links.tenant_id
    AND t.subject=koinon_chat_attachment_links.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_links.attachment_id
    AND a.tenant_id=koinon_chat_attachment_links.tenant_id
    AND a.subject=koinon_chat_attachment_links.subject
    AND a.thread_id=koinon_chat_attachment_links.thread_id)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_runs r WHERE r.id=koinon_chat_attachment_links.run_id
    AND r.tenant_id=koinon_chat_attachment_links.tenant_id
    AND r.thread_id=koinon_chat_attachment_links.thread_id
    AND r.user_message_id=koinon_chat_attachment_links.message_id))
WITH CHECK (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_links.thread_id
    AND t.tenant_id=koinon_chat_attachment_links.tenant_id
    AND t.subject=koinon_chat_attachment_links.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_links.attachment_id
    AND a.tenant_id=koinon_chat_attachment_links.tenant_id
    AND a.subject=koinon_chat_attachment_links.subject
    AND a.thread_id=koinon_chat_attachment_links.thread_id)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_runs r WHERE r.id=koinon_chat_attachment_links.run_id
    AND r.tenant_id=koinon_chat_attachment_links.tenant_id
    AND r.thread_id=koinon_chat_attachment_links.thread_id
    AND r.user_message_id=koinon_chat_attachment_links.message_id))""",
    """REVOKE ALL ON public.koinon_chat_attachment_links FROM PUBLIC""",
    """ALTER TABLE public.koinon_chat_attachment_promotions ENABLE ROW LEVEL SECURITY""",
    """ALTER TABLE public.koinon_chat_attachment_promotions FORCE ROW LEVEL SECURITY""",
    """CREATE POLICY owner_thread_scope ON public.koinon_chat_attachment_promotions
USING (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_promotions.thread_id
    AND t.tenant_id=koinon_chat_attachment_promotions.tenant_id
    AND t.subject=koinon_chat_attachment_promotions.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_promotions.attachment_id
    AND a.tenant_id=koinon_chat_attachment_promotions.tenant_id
    AND a.subject=koinon_chat_attachment_promotions.subject
    AND a.thread_id=koinon_chat_attachment_promotions.thread_id))
WITH CHECK (tenant_id=current_setting('app.attachment_tenant',true)
    AND subject=current_setting('app.attachment_subject',true)
    AND thread_id=current_setting('app.attachment_thread',true)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_threads t WHERE t.id=koinon_chat_attachment_promotions.thread_id
    AND t.tenant_id=koinon_chat_attachment_promotions.tenant_id
    AND t.subject=koinon_chat_attachment_promotions.subject)
    AND EXISTS(SELECT 1 FROM public.koinon_chat_attachments a WHERE a.id=koinon_chat_attachment_promotions.attachment_id
    AND a.tenant_id=koinon_chat_attachment_promotions.tenant_id
    AND a.subject=koinon_chat_attachment_promotions.subject
    AND a.thread_id=koinon_chat_attachment_promotions.thread_id))""",
    """REVOKE ALL ON public.koinon_chat_attachment_promotions FROM PUBLIC""",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade():
    raise RuntimeError(
        "Use a reviewed private-file restore plan; retained chat evidence must not be dropped"
    )
