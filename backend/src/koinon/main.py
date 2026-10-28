# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""ASGI entry point using native configuration and explicit deployment aliases."""

from koinon.app import create_application
from koinon.operations.configuration import environment_configuration

app = create_application(environment_configuration())
