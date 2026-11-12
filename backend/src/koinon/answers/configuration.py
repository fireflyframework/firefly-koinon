# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit rollout and database-role checks for answer attestation."""

from dataclasses import dataclass

from pyfly.config.properties.data import parse_bool
from pyfly.context.lifecycle import post_construct
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import text

from koinon.answers.release_proof_repository import AnswerReleaseProofRepository
from koinon.answers.release_proofs import AnswerReleaseProofPublisher
from koinon.operations.process import verify_isolated_process_identity


@dataclass(frozen=True)
class AnswerProofProcess:
    role: str
    username: str


async def verify_process_role(session, process):
    await verify_isolated_process_identity(session, process.username)
    row = (
        await session.execute(
            text(
                "SELECT "
                "has_function_privilege(current_user,'public.koinon_publish_release_proof(text,text,text,integer)','EXECUTE'),"
                "has_function_privilege(current_user,"
                "'public.koinon_backfill_release_proof(text,text,text,text,integer)','EXECUTE') "
            )
        )
    ).one()
    expected = (
        process.role == "worker",
        process.role == "maintenance",
    )
    if tuple(row) != expected:
        raise ValueError("Answer proof database role privileges do not match this process")
    unsafe = await session.scalar(
        text(
            "SELECT EXISTS(SELECT FROM information_schema.columns c "
            "WHERE c.table_schema='public' AND c.table_name IN "
            "('koinon_answer_release_proofs','koinon_answer_release_proof_pins',"
            "'koinon_answer_release_proof_sources','koinon_answer_release_projection_jobs') AND "
            "(has_table_privilege(current_user,'public.'||c.table_name,"
            "'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') "
            "OR has_column_privilege(current_user,'public.'||c.table_name,c.column_name,'INSERT,UPDATE')))"
        )
    )
    if unsafe:
        raise ValueError("Answer proof database role has direct mutation privileges")


class AnswerProofReadiness:
    def __init__(self, repository: AnswerReleaseProofRepository, process: AnswerProofProcess):
        self.repository = repository
        self.process = process

    @post_construct
    @transactional(read_only=True, read_from_primary=True)
    async def check(self):
        await verify_process_role(self.repository._require_session(), self.process)


def register_release_proofs(context, values):
    config = Config(values)
    if not parse_bool(config.get("koinon.answers.release_proofs.enabled", False), "answer proofs"):
        return
    role = config.get("koinon.process.role")
    key = "publisher_role" if role == "worker" else "api_role"
    default = "koinon_answer_publisher" if role == "worker" else "koinon_catalog"
    context.container.register_instance(
        AnswerProofProcess,
        AnswerProofProcess(role, config.get("koinon.answers.release_proofs." + key, default)),
    )
    for cls in (AnswerReleaseProofRepository, AnswerProofReadiness, AnswerReleaseProofPublisher):
        context.register_bean(cls)
