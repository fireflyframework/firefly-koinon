# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor

import pytest
from pyfly.core import Config
from pyfly.kernel import PayloadTooLargeException, RateLimitException

from koinon.storage.scratch import ScratchAdmission


def budget(size=1024):
    return ScratchAdmission(Config({"koinon": {"knowledge": {"ingestion": {"scratch_max_bytes": size}}}}))


def test_shared_budget_rejects_overlap_and_restores_exact_capacity_after_release():
    scratch = budget()
    with scratch.reserve(700):
        with pytest.raises(RateLimitException):
            scratch.reserve(400)
        with scratch.reserve(324):
            assert scratch.available_bytes == 0
        assert scratch.available_bytes == 324
    assert scratch.available_bytes == 1024


def test_release_is_idempotent_even_across_threads():
    scratch = budget()
    reservation = scratch.reserve(1024)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: reservation.close(), range(16)))
    assert scratch.available_bytes == 1024


@pytest.mark.parametrize("invalid", [0, -1, True, 1025])
def test_invalid_or_oversized_work_never_reserves_space(invalid):
    scratch = budget()
    with pytest.raises(PayloadTooLargeException):
        scratch.reserve(invalid)
    assert scratch.available_bytes == 1024
