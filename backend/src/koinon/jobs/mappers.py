# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from koinon.api.json_values import portable_json


def job_dto(job) -> dict:
    return {
        **{
            field: getattr(job, field)
            for field in (
                "id",
                "tenant_id",
                "resource_id",
                "kind",
                "status",
                "attempts",
                "max_attempts",
                "progress",
                "error",
            )
        },
        "result": portable_json(job.result),
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }

