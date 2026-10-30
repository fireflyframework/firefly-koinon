# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native optional-domain lookup preserves the container's binding rules."""

from pyfly.container.exceptions import NoSuchBeanError
from pyfly.kernel import ServiceUnavailableException


def native_bean(container, kind):
    try:
        return container.resolve(kind)
    except NoSuchBeanError as error:
        if error.bean_type is not kind:
            raise
        raise ServiceUnavailableException(
            f"The retained {kind.__module__.split('.')[0]} pipeline is not enabled; "
            "configure its native resources",
            code="DOMAIN_PREREQUISITE_REQUIRED",
        ) from error
