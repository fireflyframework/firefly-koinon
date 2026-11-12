# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Check source process identities and private structural publication privileges."""

from dataclasses import dataclass

from pyfly.context import ApplicationContext
from pyfly.context.lifecycle import post_construct
from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import text
from sqlalchemy.engine import make_url

from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.operations.process import verify_isolated_process_identity


@dataclass(frozen=True)
class SourceProcessIdentity:
    role: str
    username: str


async def verify_source_process(session, process: SourceProcessIdentity) -> None:
    from koinon.integrations.content_sources.structure_publication_guards import (
        ALL_SIGNATURES,
        ENTRYPOINTS,
        READ_ENTRYPOINTS,
        TABLE,
    )

    await verify_isolated_process_identity(session, process.username)
    if process.role not in {"api", "worker"}:
        raise ValueError("Source process identity requires an API or worker role")
    allowed: set[str] = set(READ_ENTRYPOINTS)
    if process.role == "worker":
        allowed.update(ENTRYPOINTS)
    functions = await session.execute(
        text(
            "SELECT signature,to_regprocedure('public.'||signature) IS NOT NULL,"
            "has_function_privilege(current_user,to_regprocedure('public.'||signature),'EXECUTE') "
            "FROM unnest(CAST(:signatures AS text[])) AS functions(signature)"
        ),
        {"signatures": list(ALL_SIGNATURES)},
    )
    if any(not installed or granted != (signature in allowed) for signature, installed, granted in functions):
        raise ValueError("Source process function privileges do not match its identity")
    permissions = (
        await session.execute(
            text(
                "SELECT has_table_privilege(current_user,'public.'||:table,'SELECT'),"
                "has_table_privilege(current_user,'public.'||:table,"
                "'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),"
                "EXISTS(SELECT FROM pg_attribute a WHERE a.attrelid=to_regclass('public.'||:table) "
                "AND a.attnum>0 AND NOT a.attisdropped AND "
                "has_column_privilege(current_user,a.attrelid,a.attnum,'INSERT,UPDATE,REFERENCES'))"
            ),
            {"table": TABLE},
        )
    ).one()
    if tuple(permissions) != (True, False, False):
        raise ValueError("Source process requires read-only access to private structure records")


class SourceProcessReadiness:
    def __init__(self, repository: SourceReadRepository, process: SourceProcessIdentity):
        self.repository = repository
        self.process = process

    @post_construct
    @transactional(read_only=True, read_from_primary=True)
    async def check(self):
        await verify_source_process(self.repository._require_session(), self.process)


def register_source_process(context: ApplicationContext) -> None:
    role = context.config.get("koinon.process.role")
    api = context.config.get("koinon.answers.release_proofs.api_role", "koinon_catalog")
    worker = context.config.get("koinon.answers.release_proofs.publisher_role", "koinon_answer_publisher")
    if (
        role not in {"api", "worker"}
        or not all(isinstance(name, str) and 1 <= len(name.encode()) <= 63 for name in (api, worker))
        or api == worker
    ):
        raise ValueError("Source process identity requires distinct bounded API and worker roles")
    username = worker if role == "worker" else api
    try:
        primary = make_url(context.config.get("pyfly.data.relational.url", ""))
    except Exception:
        raise ValueError("Source process identity requires its primary database connection") from None
    if primary.get_backend_name() != "postgresql" or primary.username != username:
        raise ValueError("Source process identity does not match its primary database connection")
    context.container.register_instance(SourceProcessIdentity, SourceProcessIdentity(role, username))
    context.register_bean(SourceProcessReadiness)
