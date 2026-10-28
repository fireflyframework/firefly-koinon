# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Frozen PyFly 26.9.4 DDL for historical migration 0016, never used by native runtime.

Native pyfly uses framework_metadata outbox tables; historical revisions must
remain executable when their original framework private constants are removed."""

_DDL_OUTBOX = """
CREATE TABLE IF NOT EXISTS pyfly_eda_outbox (
    id          BIGSERIAL PRIMARY KEY,
    destination TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL,
    headers     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pyfly_eda_outbox_dest_idx
    ON pyfly_eda_outbox (destination, id);
"""

_DDL_OFFSETS = """
CREATE TABLE IF NOT EXISTS pyfly_eda_offsets (
    consumer_group TEXT PRIMARY KEY,
    last_event_id  BIGINT NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""
