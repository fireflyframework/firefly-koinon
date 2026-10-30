# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded organization-directory filters; the server enforces visibility."""

from typing import TypedDict


class OrganizationPeopleFilter(TypedDict, total=False):
    workspace_id: str
    q: str
    job_title: str
    unit_id: str
    department_id: str
    manager_id: str
    unassigned: bool
    page: int
    page_size: int


class OrganizationUnitFilter(TypedDict, total=False):
    workspace_id: str
    parent_id: str
    q: str
    page: int
    page_size: int


class OrganizationReportsFilter(TypedDict, total=False):
    workspace_id: str
    page: int
    page_size: int
