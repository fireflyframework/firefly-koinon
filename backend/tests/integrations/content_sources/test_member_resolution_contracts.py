# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Member discovery accepts only bounded source identities and safe presentation."""

import pytest
from pydantic import ValidationError

from koinon.integrations.content_sources.sync_dtos import SourceReplacementPreviewInput


@pytest.mark.parametrize("version", ["v1\n", "v1\x00", "v1\x7f"])
def test_member_preview_rejects_control_characters_in_source_version(version):
    with pytest.raises(ValidationError):
        SourceReplacementPreviewInput(expected_revision=1, remote_version=version)
