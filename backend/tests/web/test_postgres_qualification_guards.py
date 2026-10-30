# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Check opt-in target admission without importing or starting a database context."""
import ast
import re
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

FIXTURE = Path(__file__).with_name("test_authorized_applications_postgres.py")
DATABASE = "koinon_applications_source13_" + "a" * 32


def admission(name):
    source = ast.parse(FIXTURE.read_text())
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(functions) == 1
    namespace = {"make_url": make_url, "pytest": pytest, "re": re}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(FIXTURE), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("driver", ["postgresql+psycopg", "postgresql+asyncpg"])
def test_explicit_local_source13_target_is_admitted(driver):
    target = admission("qualification_target")(f"{driver}://fixture@127.0.0.1:18783/{DATABASE}")
    assert target.host == "127.0.0.1" and target.database == DATABASE


@pytest.mark.parametrize("address", [
    f"postgresql+psycopg://fixture@external.example:18783/{DATABASE}",
    f"postgresql+psycopg://fixture@localhost:18783/{DATABASE}",
    f"postgresql+psycopg://fixture@127.0.0.1:5432/{DATABASE}",
    "postgresql+psycopg://fixture@127.0.0.1:18783/koinon",
    "postgresql+psycopg://fixture@127.0.0.1:18783/koinon_applications_qualification_retained",
    f"postgresql://fixture@127.0.0.1:18783/{DATABASE}",
])
def test_retained_or_ambiguous_database_target_is_rejected(address):
    with pytest.raises(pytest.fail.Exception):
        admission("qualification_target")(address)


@pytest.mark.parametrize("query", [
    "host=external.example", "hostaddr=203.0.113.10", "port=5432", "dbname=retained",
    "user=postgres", "service=production", "options=-csearch_path%3Dprivate",
])
def test_connection_options_cannot_override_the_admitted_target(query):
    with pytest.raises(pytest.fail.Exception):
        admission("qualification_target")(
            f"postgresql+psycopg://fixture@127.0.0.1:18783/{DATABASE}?{query}"
        )


def test_native21_registration_schema_is_required():
    validate = admission("require_native21")
    columns = {
        ("koinon_mcp_authorizations", "client_registration", "json"),
        ("koinon_authorized_applications", "client_registration", "jsonb"),
    }
    validate("koinon_0021_mcp_oauth_clients", True, columns)
    for head, table, fields in (
        ("koinon_0016_authorized_apps", True, columns),
        ("koinon_0021_mcp_oauth_clients", False, columns),
        ("koinon_0021_mcp_oauth_clients", True, set()),
        ("koinon_0021_mcp_oauth_clients", True, {(a, b, "text") for a, b, _ in columns}),
    ):
        with pytest.raises(AssertionError):
            validate(head, table, fields)
