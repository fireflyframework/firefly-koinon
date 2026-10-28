# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.kernel import ConflictException


class JobConflict(ConflictException):
    """A job identity or state conflicts with the requested operation."""
