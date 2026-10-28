# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.kernel import ForbiddenException, InvalidRequestException


class AccessDenied(ForbiddenException):
    """The selected resource is not accessible in this context."""


class InvalidHierarchy(InvalidRequestException):
    """The supplied parent is incompatible with the resource kind."""
