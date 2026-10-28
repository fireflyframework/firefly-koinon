# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import pytest
from jinja2 import UndefinedError
from pyfly.agentic.prompts import PromptTemplate as NativePromptTemplate

from flyquery.core.agents.prompt_loader import PromptTemplate, load_prompt


def test_legacy_prompt_contract_delegates_to_native_template_with_strict_rendering():
    template = PromptTemplate(
        name="scope",
        instructions="Hello {{ actor }}\n",
        user_template="{% for item in items %}\n{{ item }}\n{% endfor %}",
    )
    assert isinstance(template.native, NativePromptTemplate)
    assert template.render(actor="analyst", items=["one", "two"]) == ("Hello analyst", "one\ntwo\n")
    with pytest.raises(UndefinedError):
        template.render(items=[])


def test_yaml_prompt_loads_native_metadata_and_keeps_legacy_fields():
    template = load_prompt("grounding")
    assert isinstance(template.native, NativePromptTemplate)
    assert template.native.system_template == template.instructions
    assert template.native.version == "1.0.0"
    assert template.native.name == template.name
