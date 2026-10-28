# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Public composition boundary; importing this module starts no server."""

from sqlalchemy import MetaData


def canon_metadata() -> MetaData:
    """Return all canon business tables for the root migration environment."""
    from flycanon.models.entities import Base

    return Base.metadata
