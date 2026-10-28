# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Compatibility view over native PyFly YAML prompt templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

import yaml
from jinja2 import StrictUndefined
from pyfly.agentic.prompts import PromptLoader
from pyfly.agentic.prompts import PromptTemplate as NativePromptTemplate


@dataclass(slots=True)
class PromptTemplate:
    system: str
    user_template: str
    name: str = ""
    version: str = "1.0.0"
    native: NativePromptTemplate = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.native = PromptLoader.from_string(
            self.name,
            self.system,
            self.user_template,
            version=self.version,
        )
        # Native defaults are permissive; retain the existing strict whitespace contract.
        for key, source in (("system", self.system), ("user", self.user_template)):
            if source:
                compiled = self.native._compiled[key]
                environment = compiled.environment.overlay(
                    undefined=StrictUndefined,
                    trim_blocks=True,
                    lstrip_blocks=True,
                    keep_trailing_newline=False,
                )
                self.native._compiled[key] = environment.from_string(source)

    def render(self, **variables: Any) -> tuple[str, str]:
        if self.native.system_template != self.system or self.native.user_template != self.user_template:
            self.__post_init__()
        prompt = self.native.render(**variables)
        return prompt.system, prompt.user


def load_prompt(name: str) -> PromptTemplate:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise FileNotFoundError(f"prompt {name!r} not found")
    resource = files("flycanon.resources.prompts").joinpath(f"{name}.yaml")
    data = yaml.safe_load(resource.read_text(encoding="utf-8")) or {}
    return PromptTemplate(
        system=str(data.get("system") or ""),
        user_template=str(data.get("user") or ""),
        name=name,
        version=str(data.get("version") or "1.0.0"),
    )
