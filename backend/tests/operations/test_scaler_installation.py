# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.workers.scaler_installation import validate_role_names


@pytest.mark.parametrize(
    "owner,reader", [("same", "same"), ("Bad", "reader"), ("owner", "x;DROP ROLE x"), ("postgres", "reader")]
)
def test_operator_rejects_ambiguous_or_unsafe_roles(owner, reader):
    with pytest.raises(ValueError):
        validate_role_names(owner, reader)


def test_scaler_roles_are_distinct_fixed_identifiers():
    assert validate_role_names("koinon_demand_owner", "koinon_demand_reader") is None
