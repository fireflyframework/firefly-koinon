# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.mcp_applications.entities import McpOAuthClientRegistration


@repository(name="mcp.applications.repository")
class McpOAuthClientRepository(Repository[McpOAuthClientRegistration, str]):
    pass
