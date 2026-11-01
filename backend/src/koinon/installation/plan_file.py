# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Protected operator inputs contain references, never inline provider credentials."""

import os
import stat
from collections.abc import Mapping
from pathlib import Path

from pydantic import SecretStr

from koinon.installation.dtos import InstallationPlan


def load_plan(path: Path) -> InstallationPlan:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        observed = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_mode & 0o077
            or observed.st_uid != os.getuid()
            or observed.st_size > 262144
        ):
            raise ValueError("Use an owner-only regular installation file of at most 256 KiB")
        value = stream.read(262145)
    if len(value) > 262144:
        raise ValueError("Use an owner-only regular installation file of at most 256 KiB")
    try:
        return InstallationPlan.model_validate_json(value)
    except ValueError:
        raise ValueError("The installation manifest is invalid") from None


def resolve_secrets(plan: InstallationPlan, environment: Mapping[str, str]) -> dict[str, SecretStr | None]:
    result: dict[str, SecretStr | None] = {}
    for provider in plan.providers:
        value = environment.get(provider.secret_env, "") if provider.secret_env else ""
        if (
            (provider.kind != "ollama" and not value)
            or len(value) > 16384
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("A declared provider credential is missing or invalid")
        result[provider.key] = SecretStr(value) if value else None
    return result
