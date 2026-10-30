# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Start the configured application listener through native PyFly server adapters."""
import importlib.util
import os

from pyfly.core import Config
from pyfly.server import ApplicationServerPort, EventLoopPort
from pyfly.server.auto_configuration import EventLoopAutoConfiguration, ServerAutoConfiguration

from koinon.mcp.endpoints import listener_properties, resolve_mcp_configuration
from koinon.operations.configuration import environment_configuration


def application_server(kind: str) -> ApplicationServerPort:
    factories = ServerAutoConfiguration()
    choices = (("granian", factories.granian_server), ("uvicorn", factories.uvicorn_server),
               ("hypercorn", factories.hypercorn_server))
    if kind not in {"auto", "granian", "uvicorn", "hypercorn"}:
        raise ValueError("Configure a supported native PyFly server type")
    for name, factory in choices:
        if kind in {"auto", name} and importlib.util.find_spec(name) is not None:
            return factory()
    raise ValueError("The configured native PyFly server is not installed")


def event_loop(kind: str) -> EventLoopPort:
    factories = EventLoopAutoConfiguration()
    if kind not in {"auto", "asyncio", "uvloop", "winloop"}:
        raise ValueError("Configure a supported native PyFly event loop")
    for name, factory in (("uvloop", factories.uvloop), ("winloop", factories.winloop)):
        if kind in {"auto", name} and importlib.util.find_spec(name) is not None:
            return factory()
    if kind in {"auto", "asyncio"}:
        return factories.asyncio_loop()
    raise ValueError("The configured native PyFly event loop is not installed")


def main():
    config = Config(resolve_mcp_configuration(environment_configuration()))
    properties = listener_properties(config)
    server = application_server(properties.type)
    loop = event_loop(properties.event_loop)
    loop.install()
    os.environ["_PYFLY_SERVER_HOST"] = properties.host
    os.environ["_PYFLY_SERVER_PORT"] = str(properties.port)
    os.environ["_PYFLY_SERVER_TYPE"] = server.server_info.name
    server.serve("koinon.main:app", properties)


if __name__ == "__main__":
    main()
