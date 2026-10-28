# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.profiles.dtos import ProfileOutput
from koinon.profiles.entities import Profile


def profile_dto(row: Profile) -> dict:
    return ProfileOutput.model_validate(
        {
            "subject": row.subject,
            "display_name": row.display_name,
            "locale": row.locale,
            "time_zone": row.time_zone,
            "response_language": row.response_language,
            "avatar_url": ("/api/v1/profile/avatar?v=" + row.avatar_version) if row.avatar_version else None,
            "avatar_version": row.avatar_version,
        }
    ).model_dump()
