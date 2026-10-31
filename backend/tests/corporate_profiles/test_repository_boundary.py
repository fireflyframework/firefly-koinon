# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Keep the admitted CIAM orchestration boundary independent of SQL construction."""

import ast
from pathlib import Path


def test_ciam_orchestration_does_not_construct_or_execute_database_queries():
    source = Path(__file__).parents[2] / "src/koinon"
    for relative in (
        "corporate_profiles/service.py",
        "corporate_profiles/projector.py",
        "corporate_profiles/refresh.py",
        "organization_people/service.py",
        "organization_people/claims.py",
    ):
        tree = ast.parse((source / relative).read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert "sqlalchemy" not in imports, relative
        assert not any(
            isinstance(node, ast.Attribute) and node.attr in {"_require_session", "resource", "begin_nested"}
            for node in ast.walk(tree)
        ), relative


def test_private_claim_evidence_marker_is_not_a_wire_field():
    from koinon.corporate_profiles.dtos import OrganizationPresentation

    assert "claims_observed_at" not in str(OrganizationPresentation.model_json_schema())
