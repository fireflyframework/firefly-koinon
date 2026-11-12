# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One explicit process role owns background consumption."""

from copy import deepcopy
from typing import Literal

from pyfly.config.properties.data import parse_bool
from pyfly.core import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

ProcessRole = Literal["api", "worker"]


async def verify_isolated_process_identity(session, username: str) -> None:
    """Check a direct ordinary login; feature readiness owns its exact function grants."""
    row = (
        await session.execute(
            text(
                "SELECT current_user,session_user,r.rolcanlogin,r.rolsuper,r.rolinherit,r.rolcreatedb,"
                "r.rolcreaterole,r.rolreplication,r.rolbypassrls,"
                "EXISTS(SELECT FROM pg_auth_members m WHERE m.member=r.oid OR m.roleid=r.oid) "
                "FROM pg_roles r WHERE r.rolname=current_user"
            )
        )
    ).one()
    if tuple(row) != (username, username, True, False, False, False, False, False, False, False):
        raise ValueError("Process database identity must be an isolated ordinary login")


def process_configuration(values: dict, *, role: ProcessRole | None = None) -> dict:
    result = deepcopy(values)
    configured = Config(values).get("koinon.process.role")
    selected = configured if configured is not None else role or "api"
    if not isinstance(selected, str) or selected not in {"api", "worker"} or role and selected != role:
        raise ValueError("koinon.process.role must match the api or worker entrypoint")
    worker = selected == "worker"
    result.setdefault("koinon", {}).setdefault("process", {})["role"] = selected
    proof = Config(result).get("koinon.answers.release_proofs", {})
    if parse_bool(proof.get("enabled", False), "koinon.answers.release_proofs.enabled"):
        api_role = proof.get("api_role", "koinon_catalog")
        publisher_role = proof.get("publisher_role", "koinon_answer_publisher")
        if (
            not all(
                isinstance(name, str) and 1 <= len(name.encode()) <= 63 for name in (api_role, publisher_role)
            )
            or api_role == publisher_role
        ):
            raise ValueError("Answer proof roles must be distinct bounded database identities")
        try:
            primary = make_url(Config(result).get("pyfly.data.relational.url", ""))
        except Exception:
            raise ValueError("Answer proof process role requires its primary database connection") from None
        if primary.get_backend_name() != "postgresql" or primary.username != (
            publisher_role if worker else api_role
        ):
            raise ValueError("Answer proof process role does not match its primary database identity")
    scheduling = result.setdefault("pyfly", {}).setdefault("scheduling", {})
    scheduling["enabled"] = worker
    effective = Config(result).get("pyfly.scheduling.enabled")
    if parse_bool(effective, "pyfly.scheduling.enabled") != worker:
        raise ValueError("pyfly.scheduling.enabled must match koinon.process.role")
    knowledge = result["koinon"].setdefault("knowledge", {})
    knowledge.setdefault("indexes", {})["enabled"] = worker
    knowledge.setdefault("mode_preparation", {})["enabled"] = worker
    result["koinon"].setdefault("attachments", {})["worker_enabled"] = worker
    result["koinon"].setdefault("identity", {}).setdefault("profile_sync", {})["worker_enabled"] = worker
    bulk = knowledge.setdefault("bulk", {})
    for key in ("worker_enabled", "query_worker_enabled"):
        if worker:
            bulk[key] = parse_bool(Config(result).get("koinon.knowledge.bulk." + key, False), key)
        else:
            bulk[key] = False
            if parse_bool(Config(result).get("koinon.knowledge.bulk." + key), key):
                raise ValueError("The API role does not enable bulk background workers")
    if worker:
        result["pyfly"].setdefault("mcp", {}).setdefault("sessions", {})["enabled"] = False
        if parse_bool(Config(result).get("pyfly.mcp.sessions.enabled"), "pyfly.mcp.sessions.enabled"):
            raise ValueError("A complete worker does not enable MCP sessions")
    return result
