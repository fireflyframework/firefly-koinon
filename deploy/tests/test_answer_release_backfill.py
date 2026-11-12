# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Maintenance command failures never print credentials or protected driver details."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "backfill_answer_release_proofs.py"
spec = importlib.util.spec_from_file_location("answer_backfill_cli", PATH)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sqlite:///test.db",
        "postgresql://postgres@localhost/app",
        "postgresql://koinon_catalog@localhost/app",
    ],
)
def test_maintenance_requires_its_own_postgresql_identity(value):
    with pytest.raises(ValueError):
        cli.connection_url(value)


def test_invalid_connection_error_does_not_echo_input():
    value = "bad-scheme://PRIVATE_CREDENTIAL_CONTENT"
    with pytest.raises(ValueError) as error:
        cli.connection_url(value)
    assert "PRIVATE_CREDENTIAL_CONTENT" not in str(error.value)


def test_driver_failure_is_sanitized_and_returns_nonzero(monkeypatch, capsys):
    async def fail(_args):
        raise RuntimeError("password=PRIVATE_CREDENTIAL protected-answer=PRIVATE_EVIDENCE")

    monkeypatch.setattr(cli, "execute", fail)
    assert cli.main(["--job", "integrity-audit"]) == 1
    output = capsys.readouterr()
    assert "unavailable" in output.out
    assert "PRIVATE_CREDENTIAL" not in output.out + output.err
    assert "PRIVATE_EVIDENCE" not in output.out + output.err


def test_unfinished_job_never_reports_success(monkeypatch, capsys):
    async def unfinished(_args):
        return {"state": "running", "processed": 25, "endpoint_enabled": False}

    monkeypatch.setattr(cli, "execute", unfinished)
    assert cli.main(["--job", "resume-me"]) == 2
    assert '"endpoint_enabled": false' in capsys.readouterr().out
