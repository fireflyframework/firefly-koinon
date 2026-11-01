# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exercise the standalone generator without replacing final integrated SDK artifacts."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from koinon.answers.receipts import AnswerRelease
from koinon.assistants.audit_dtos import AnswerAudit


def generated(monkeypatch):
    root = Path(__file__).parents[3]
    monkeypatch.syspath_prepend(str(root / "sdk/python/src"))
    spec = importlib.util.spec_from_file_location(
        "release_contract_generator", root / "tools/sdk/generate_python_connections.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    outputs = {}
    for name in ("answer_release", "answer_audit"):
        module = ModuleType("koinon_sdk." + name)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        exec(generator.render(root / generator.SOURCES[name]), module.__dict__)
        outputs[name] = module
    return outputs["answer_release"].AnswerRelease, outputs["answer_audit"].AnswerAudit


def receipt():
    return AnswerRelease(
        run_id="run",
        message_id="message",
        tenant_id="tenant",
        publication_sequence=1,
        outcome="refused",
        text_sha256="a" * 64,
        citations_sha256="b" * 64,
        artifacts_sha256="c" * 64,
        policy_sha256="d" * 64,
        created_at=datetime.now(UTC),
    )


def test_standalone_receipt_retains_all_typed_fields_and_constraints(monkeypatch):
    sdk_release, _ = generated(monkeypatch)
    native, client = AnswerRelease.model_json_schema(), sdk_release.model_json_schema()
    assert native["properties"] == client["properties"]
    assert native["required"] == client["required"]
    for key in ("properties", "required"):
        assert native["$defs"]["ResultPin"][key] == client["$defs"]["ResultPin"][key]
    assert sdk_release.model_validate_json(receipt().model_dump_json()).policy_version == "knowledge-only-v1"
    invalid = {**receipt().model_dump(mode="json"), "text_sha256": "not-a-digest"}
    for model in (AnswerRelease, sdk_release):
        with pytest.raises(ValidationError):
            model.model_validate(invalid)


def test_audit_receipt_is_additive_and_legacy_audits_do_not_gain_invented_proof(monkeypatch):
    _, sdk_audit = generated(monkeypatch)
    old = {"run_id": "old", "provenance_status": "not_recorded"}
    new = {
        "run_id": "run",
        "provenance_status": "recorded",
        "output_release": receipt().model_dump(mode="json"),
    }
    for model in (AnswerAudit, sdk_audit):
        assert model.model_validate(old).output_release is None
        assert model.model_validate(new).output_release.message_id == "message"
