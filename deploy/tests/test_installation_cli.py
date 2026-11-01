# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "bootstrap_knowledge_cli", Path(__file__).parents[1] / "bootstrap_knowledge.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def test_validate_only_does_not_import_application_or_resolve_credentials(
    tmp_path, capsys, monkeypatch
):
    from koinon.installation.dtos import InstallationPlan

    values = {
        "schema_version": 1,
        "plan_key": "first-start",
        "tenant_id": "example",
        "providers": [
            {
                "key": "local",
                "name": "Local",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["model"],
            }
        ],
        "catalog": [{"key": "shared", "name": "Shared", "kind": "workspace"}],
        "agent": {
            "key": "guide",
            "name": "Guide",
            "provider_key": "local",
            "model_id": "model",
        },
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(values))
    path.chmod(0o600)
    # An imported application here would make source validation dependent on runtime services.
    monkeypatch.setitem(sys.modules, "koinon.main", None)
    await module.main(["--manifest", str(path), "--validate-only"])
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "source_valid"
    assert (
        result["plan_sha256"] == InstallationPlan.model_validate(values).fingerprint()
    )
