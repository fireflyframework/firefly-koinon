# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Compatibility access to application-owned native datasource resources."""

from __future__ import annotations

from pyfly.data.relational.datasource_registry import DataSource, DataSourceRegistry
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from flycanon.web.conventions.db import install_tenant_guc_hook


def build_engine(
    database_url: str,
    *,
    echo: bool = False,
    registry: DataSourceRegistry | None = None,
    datasource_name: str = "canon",
) -> AsyncEngine:
    """Borrow a named engine; URL and echo never provision or reconfigure it."""
    return _named_source(database_url, registry, datasource_name).engine


def build_session_factory(
    database_url: str,
    *,
    echo: bool = False,
    registry: DataSourceRegistry | None = None,
    datasource_name: str = "canon",
) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Borrow both resources from the same named datasource."""
    source = _named_source(database_url, registry, datasource_name)
    return source.sessionmaker, source.engine


def _named_source(database_url: str, registry: DataSourceRegistry | None, datasource_name: str) -> DataSource:
    if registry is None:
        raise RuntimeError("Use the ApplicationContext-owned DataSourceRegistry for document repositories")
    source = registry.get(datasource_name)
    try:
        url = make_url(database_url)
    except (ArgumentError, TypeError, ValueError):
        raise ValueError("Configure a valid repository database URL") from None
    if url != source.engine.url:
        raise ValueError("The repository URL must match the named native datasource")
    install_tenant_guc_hook()
    return source
