# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import pytest
from jinja2 import UndefinedError
from pyfly.agentic.prompts import PromptTemplate as NativePromptTemplate

from flycanon.core.services.consolidation.prompt_loader import PromptTemplate, load_prompt


def test_canon_prompt_delegates_to_native_template_and_preserves_strict_legacy_tuple():
    template = PromptTemplate(
        system="Hello {{ actor }}\n",
        user_template="{% for item in items %}\n{{ item }}\n{% endfor %}",
        name="scope",
    )
    assert isinstance(template.native, NativePromptTemplate)
    assert template.render(actor="analyst", items=["one", "two"]) == ("Hello analyst", "one\ntwo\n")
    with pytest.raises(UndefinedError):
        template.render(items=[])


def test_canon_yaml_uses_native_template_and_keeps_legacy_system_field():
    template = load_prompt("consolidation")
    assert isinstance(template.native, NativePromptTemplate)
    assert template.native.system_template == template.system
