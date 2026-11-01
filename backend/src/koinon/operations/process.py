# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One explicit process role owns background consumption."""

from copy import deepcopy
from typing import Literal

from pyfly.config.properties.data import parse_bool
from pyfly.core import Config

ProcessRole = Literal["api", "worker"]


def process_configuration(values: dict, *, role: ProcessRole | None = None) -> dict:
    result = deepcopy(values)
    configured = Config(values).get("koinon.process.role")
    selected = configured if configured is not None else role or "api"
    if not isinstance(selected, str) or selected not in {"api", "worker"} or role and selected != role:
        raise ValueError("koinon.process.role must match the api or worker entrypoint")
    worker = selected == "worker"
    result.setdefault("koinon", {}).setdefault("process", {})["role"] = selected
    scheduling = result.setdefault("pyfly", {}).setdefault("scheduling", {})
    scheduling["enabled"] = worker
    effective = Config(result).get("pyfly.scheduling.enabled")
    if parse_bool(effective, "pyfly.scheduling.enabled") != worker:
        raise ValueError("pyfly.scheduling.enabled must match koinon.process.role")
    knowledge = result["koinon"].setdefault("knowledge", {})
    knowledge.setdefault("indexes", {})["enabled"] = worker
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
