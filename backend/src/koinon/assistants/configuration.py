# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.agentic.models import ModelFactory
from pyfly.container import bean, configuration


@configuration
class AssistantConfiguration:
    @bean(name="assistants.model_factory")
    def model_factory(self) -> ModelFactory:
        return ModelFactory()
