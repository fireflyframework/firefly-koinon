# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import bean, configuration

from koinon.catalog.service import CatalogService
from koinon.security.identity import MembershipAuthorizer


@configuration
class ApplicationConfiguration:
    @bean(name="koinon.membership_authorizer")
    def membership_authorizer(self, catalog: CatalogService) -> MembershipAuthorizer:
        return catalog
