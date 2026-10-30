# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Launch through the public native pre-loop boundary, then one ASGI lifecycle."""

from pyfly.core import Config
from pyfly.server import ApplicationServerPort, EventLoopPort, launch

from koinon.mcp.endpoints import listener_properties, resolve_mcp_configuration
from koinon.operations.configuration import environment_configuration


def main(*, server: ApplicationServerPort | None = None, event_loop: EventLoopPort | None = None):
    config = Config(resolve_mcp_configuration(environment_configuration()))
    properties = listener_properties(config)
    launch("koinon.main:app", properties, server=server, event_loop=event_loop)


if __name__ == "__main__":
    main()
