# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Results of source intake lifecycle operations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceRemoval:
    """What :meth:`IntakeService.remove` actually did.

    ``original_deleted`` is the fact the audit row, the ``SourceRemoved``
    event and the workspace purge counter all report. It is returned
    rather than left implicit so no caller has to guess it from the
    row it read before the call: the purge service did exactly that in
    the first 26.7.1 cut (counted ``object_store_key`` being set) and
    reported ``originals_deleted: 2`` for two originals that were still
    on disk, because the API process's object store was not the one the
    worker had written to.
    """

    source_id: str
    original_deleted: bool
