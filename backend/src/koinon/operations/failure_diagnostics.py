# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded failure locations without exception messages, source lines or local values."""

import re


def _identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,159}", value) else None


def failure_metadata(error: BaseException) -> list[dict]:
    try:
        return _collect_failure_metadata(error)
    except Exception:
        return [{"error_type": "Unavailable", "frames": []}]


def _collect_failure_metadata(error: BaseException) -> list[dict]:
    pending, seen, records = [error], set(), []
    while pending and len(records) < 8:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        frames = []
        trace = current.__traceback__
        while trace is not None:
            frames.append(
                {
                    "module": _identifier(trace.tb_frame.f_globals.get("__name__")),
                    "function": _identifier(trace.tb_frame.f_code.co_name),
                    "line": trace.tb_lineno,
                }
            )
            frames = frames[-4:]
            trace = trace.tb_next
        records.append(
            {
                "error_type": _identifier(type(current).__name__),
                "frames": frames,
            }
        )
        nested = current.__cause__ or current.__context__
        if nested is not None:
            pending.append(nested)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions[:8])
    return records
