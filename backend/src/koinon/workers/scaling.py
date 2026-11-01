# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fixed counts-only PostgreSQL demand derived from the native queue specifications."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.sql.selectable import TableClause

from koinon.operations.settings import OperationalSettings
from koinon.workers.observations import queue_specifications, queue_statement

FUNCTION_SCHEMA = "koinon_operations"
FUNCTION_NAME = "worker_demand_v1"
FUNCTION_QUERY = "SELECT koinon_operations.worker_demand_v1()"
_REQUIRED = ("primary", "canon", "canon_admin", "structured", "structured_admin")


@dataclass(frozen=True)
class ScalingLimits:
    document_lease_seconds: int = 600
    document_max_attempts: int = 3
    structured_lease_seconds: int = 1800
    structured_max_attempts: int = 3
    queue_rows: int = 100000

    def __post_init__(self):
        for value, maximum in (
            (self.document_lease_seconds, 86400),
            (self.document_max_attempts, 100),
            (self.structured_lease_seconds, 86400),
            (self.structured_max_attempts, 100),
            (self.queue_rows, 100000),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Scaling limits require the effective bounded native worker settings")


@dataclass(frozen=True)
class DemandFunction:
    sql: str
    query: str
    queues: tuple[str, ...]
    columns: dict[str, tuple[str, ...]]
    sha256: str


def require_colocated_postgres(urls: Mapping[str, str]):
    if not set(_REQUIRED) <= set(urls):
        raise ValueError("All worker bindings must select the same PostgreSQL database")
    identities = set()
    for value in urls.values():
        try:
            url = make_url(value)
            if url.get_backend_name() != "postgresql" or not url.database:
                raise ValueError()
            if {"dbname", "database", "hostaddr", "service", "servicefile"} & set(url.query):
                raise ValueError()
            query_host = url.query.get("host")
            if query_host is not None and (
                not isinstance(query_host, str)
                or (url.host and query_host.rstrip(".").lower() != url.host.rstrip(".").lower())
            ):
                raise ValueError()
            host = query_host or url.host
            if not isinstance(host, str) or not host or "," in host:
                raise ValueError()
            port_value = url.query.get("port", "5432")
            if not isinstance(port_value, str):
                raise ValueError()
            query_port = int(port_value)
            if url.port is not None and "port" in url.query and url.port != query_port:
                raise ValueError()
            port = url.port or query_port
            if not 1 <= port <= 65535:
                raise ValueError()
            identities.add((host.rstrip(".").lower(), port, url.database))
        except (ValueError, TypeError, ArgumentError):
            raise ValueError("All worker bindings must select the same PostgreSQL database") from None
    if len(identities) != 1:
        raise ValueError("All worker bindings must select the same PostgreSQL database")
    return identities.pop()


def render_demand_function(limits: ScalingLimits) -> DemandFunction:
    specs = queue_specifications(
        sa.func.current_timestamp(),
        OperationalSettings(),
        canon=SimpleNamespace(
            ingest_timeout_s=limits.document_lease_seconds, ingest_max_attempts=limits.document_max_attempts
        ),
        structured=SimpleNamespace(
            processing_lease_s=limits.structured_lease_seconds,
            ingest_max_attempts=limits.structured_max_attempts,
        ),
        schema="public",
    )
    columns = {}
    queries = []
    for spec in specs:
        observed = queue_statement(
            spec.table, spec.ready, spec.active, spec.retry, spec.created, limit=limits.queue_rows
        )
        for node in visitors.iterate(observed):
            if isinstance(node, ColumnClause) and isinstance(node.table, TableClause):
                columns.setdefault(node.table.name, set()).add(node.name)
        observed = observed.subquery()
        queries.append(sa.select(sa.func.least(observed.c.total, limits.queue_rows).label("demand")))
    combined = sa.union_all(*queries).subquery()
    statement = sa.select(sa.cast(sa.func.coalesce(sa.func.sum(combined.c.demand), 0), sa.BigInteger))
    body = str(
        statement.compile(
            dialect=postgresql.dialect(),
            schema_translate_map={None: "public"},
            render_schema_translate=True,
            compile_kwargs={"literal_binds": True},
        )
    )
    if set(columns) & {"question", "payload"} or any(
        {"question", "payload", "request_json", "text", "content"} & values for values in columns.values()
    ):
        raise ValueError("A scaler cannot read work payloads")
    sql = (
        f"CREATE OR REPLACE FUNCTION {FUNCTION_SCHEMA}.{FUNCTION_NAME}() RETURNS bigint\n"
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog\n"
        f"AS $koinon_scaler$\n{body}\n$koinon_scaler$;"
    )
    return DemandFunction(
        sql,
        FUNCTION_QUERY,
        tuple(spec.name for spec in specs),
        {table: tuple(sorted(values)) for table, values in sorted(columns.items())},
        sha256(sql.encode()).hexdigest(),
    )
