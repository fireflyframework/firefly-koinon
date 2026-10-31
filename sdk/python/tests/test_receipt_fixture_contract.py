# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import pytest

from koinon_sdk import AnswerAudit, RlmToolReceipt


@pytest.mark.parametrize("model", [RlmToolReceipt, AnswerAudit])
def test_generated_rlm_receipt_fixtures_satisfy_the_actual_typed_client(model):
    root = Path(__file__).resolve().parents[3]
    fixtures = json.loads((root / "sdk/contract/fixtures.json").read_text())["fixtures"]
    assert model.model_validate(fixtures[model.__name__]) is not None
