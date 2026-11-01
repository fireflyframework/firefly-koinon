# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import pytest
from test_installation_manifest import example

from koinon.installation.plan_file import load_plan, resolve_secrets


def test_load_owner_only_manifest_and_resolve_only_declared_env_credentials(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(example()))
    path.chmod(0o600)
    plan = load_plan(path)
    values = resolve_secrets(
        plan, {"INSTALL_CHAT_KEY": "chat-key", "INSTALL_EMBEDDING_KEY": "embed-key", "UNRELATED": "ignored"}
    )
    assert set(values) == {"chat", "embedding"}
    assert values["chat"].get_secret_value() == "chat-key"
    assert "chat-key" not in repr(values)


@pytest.mark.parametrize("unsafe", ["mode", "symlink", "oversize"])
def test_unsafe_plan_files_fail_before_parsing(tmp_path, unsafe):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(example()))
    path.chmod(0o600)
    if unsafe == "mode":
        path.chmod(0o644)
    elif unsafe == "symlink":
        target = tmp_path / "target.json"
        path.rename(target)
        path.symlink_to(target)
    else:
        path.write_bytes(b" " * 262145)
    with pytest.raises((ValueError, OSError)):
        load_plan(path)


def test_missing_or_multiline_credentials_do_not_echo_secret_or_env_contents():
    plan = __import__(
        "koinon.installation.dtos", fromlist=["InstallationPlan"]
    ).InstallationPlan.model_validate(example())
    for values in ({}, {"INSTALL_CHAT_KEY": "secret\nheader", "INSTALL_EMBEDDING_KEY": "ok"}):
        with pytest.raises(ValueError) as error:
            resolve_secrets(plan, values)
        assert "secret" not in str(error.value).lower()
        assert "header" not in str(error.value)
