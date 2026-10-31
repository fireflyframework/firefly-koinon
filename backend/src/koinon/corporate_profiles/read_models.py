# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable internal read facts; these are not public request or response DTOs."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.sql import Select

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.entities import CorporateProfileSnapshot as Snapshot
from koinon.corporate_profiles.entities import OrganizationPresentationPreference as Preference
from koinon.organization_people.entities import OrganizationProfileMappingRecord as Mapping
from koinon.profiles.entities import Profile
from koinon.tokens.entities import PersonalToken


@dataclass(frozen=True, slots=True)
class RevisionFact:
    id: str
    revision: int


@dataclass(frozen=True, slots=True)
class PresentationRead:
    actor: str
    tenant_id: str
    wanted: frozenset[str]
    workspace_id: str | None
    own: bool
    authors: bool
    token_id: str
    count_query: Select[Any] | None = None
    expected_total: int | None = None
    people: tuple[RevisionFact, ...] = ()
    units: tuple[RevisionFact, ...] = ()
    unassigned: tuple[str, ...] = ()
    page_query: Select[Any] | None = None
    page_subjects: tuple[str, ...] = ()
    author_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PresentationRecord:
    subject: str | None
    profile: Profile | None
    snapshot: Snapshot | None
    preference: Preference | None
    provider: CorporateProvider | None
    mapping: Mapping | None
    token: PersonalToken | None
    active_policy: bool
    name_required: bool
    avatar_required: bool
    overrides_allowed: bool
    current_member: bool
