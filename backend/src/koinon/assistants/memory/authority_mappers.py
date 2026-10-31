# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure fixed-set material partitioning and dynamic conversation availability."""

import json

from koinon.assistants.memory.mappers import digest, material_digest, normalized_scope, text_digest
from koinon.assistants.memory.projections import MemoryAuthorityStamp as MemoryAuthorityStamp
from koinon.catalog.errors import AccessDenied


def partition_material(rows, values, current_evidence=()):
    """Reuse deduplicated database rows for each fixed manifest; no policy is evaluated here."""
    by_tag = {}
    for item in rows:
        by_tag.setdefault(item[0], []).append(item)
    entries = {item[1]: item for item in by_tag.get("entry", [])}
    if any(item[1] not in {"true", "True", "1"} for item in by_tag.get("result_budget", [])):
        raise AccessDenied("Request a smaller conversation page", code="MEMORY_PAGE_TOO_WIDE")
    if any(item[2] not in {"true", "True", "1"} for item in by_tag.get("capture_check", [])):
        raise AccessDenied("Conversation changed before delivery", code="MEMORY_UNAVAILABLE")
    current_sha256 = current_material(by_tag, current_evidence) if current_evidence else None
    output = {"__current__": MemoryAuthorityStamp("", "", {}, current_sha256)} if current_evidence else {}
    shared = {"deployment", "org_policy", "membership"}
    for value in values:
        runs = {ref.run_id for ref in value.dependencies}
        results = {pin.id for ref in value.dependencies for pin in ref.result_pins}
        generations = {ref.generation_id for ref in value.dependencies if ref.generation_id}
        threads = {value.thread_id, *(ref.thread_id for ref in value.dependencies)}
        messages = {key for ref in value.dependencies for key in (ref.user_message_id, ref.answer_message_id)}
        assets = set(value.asset_ids)
        roots = [item for item in by_tag.get("curated_root", []) if item[3] in assets]
        ancestry = assets | {item[5] for item in roots}
        for _ in range(16):
            expanded = ancestry | {entries[key][5] for key in ancestry if key in entries and entries[key][5]}
            if expanded == ancestry:
                break
            ancestry = expanded
        tokens = {value.origin_token_id, *(ref.origin_token_id for ref in value.dependencies)}
        tokens.update(item[2] for item in by_tag.get("target_origin", []) if item[1] == value.run_id)
        tokens.update(item[5] for item in by_tag.get("result", []) if item[2] in runs)
        token_rows = [item for item in by_tag.get("token", []) if item[1] in tokens]
        apps = {item[5] for item in token_rows if item[5]}
        app_rows = [item for item in by_tag.get("application", []) if item[1] in apps]
        clients = {item[3] for item in app_rows}
        allowed = {
            "target_origin": lambda item, run=value.run_id: item[1] == run,
            "thread": lambda item, captured=threads: item[1] in captured,
            "thread_private": lambda item, captured=threads: item[1] in captured,
            "folder": lambda item, folder=value.folder_id: item[1] == folder,
            "run": lambda item, captured=runs: item[1] in captured,
            "message": lambda item, captured=messages: item[1] in captured,
            "result": lambda item, captured=results: item[1] in captured,
            "manifest": lambda item, captured=generations: item[1] in captured,
            "entry": lambda item, captured=ancestry: item[1] in captured,
            "binding": lambda item, captured=ancestry: item[3] in captured,
            "curated_state": lambda item, captured=assets: item[1] in captured,
            "curated_root": lambda item, captured=assets: item[3] in captured,
            "token": lambda item, captured=tokens: item[1] in captured,
            "application": lambda item, captured=apps: item[1] in captured,
            "registration": lambda item, captured=clients: item[3] in captured,
        }
        origin = [
            item
            for tag, items in by_tag.items()
            for item in items
            if tag in shared or tag in allowed and allowed[tag](item)
        ]
        callers = [item for tag, items in by_tag.items() if tag.startswith("caller/") for item in items]
        output[value.generation_id] = MemoryAuthorityStamp(
            material_digest(origin),
            material_digest(origin + callers),
            source_availability(value, by_tag),
            current_sha256,
        )
    return output


def source_availability(value, rows):
    """Describe current context eligibility; this never grants historical answer access."""
    threads = {item[1]: item for item in rows.get("thread", [])}
    folders = {item[1]: item for item in rows.get("folder", [])}
    messages = {item[1]: item for item in rows.get("message", [])}
    runs = {item[1]: item for item in rows.get("run", [])}
    private = {item[1]: item[2] for item in rows.get("thread_private", [])}
    org = rows.get("org_policy", [])
    raw_policy = json.loads(org[0][3]) if org and org[0][3] else None
    enabled = (raw_policy or {}).get("allow_project_memory", True)
    source_folder = folders.get(value.folder_id)
    consent = enabled and source_folder is not None and source_folder[8] in {"true", "True", "1"}
    output = {}
    for ref in value.dependencies:
        thread = threads.get(ref.thread_id)
        user, answer = messages.get(ref.user_message_id), messages.get(ref.answer_message_id)
        run = runs.get(ref.run_id)
        if thread is None or thread[7] is not None:
            state = "deleted"
        elif thread[2] != value.tenant_id or thread[3] != value.subject:
            state = "unverified"
        elif thread[6] is not None:
            state = "archived"
        elif value.mode == "personal_project" and thread[4] != value.folder_id:
            state = "moved"
        elif value.mode == "personal_project" and not consent:
            state = "memory_disabled"
        elif value.mode == "personal_project" and private.get(ref.thread_id) in {"true", "True", "1"}:
            state = "unverified"
        elif (
            user is None
            or answer is None
            or run is None
            or run[6] != "completed"
            or text_digest(user[4] or "") != ref.user_sha256
            or text_digest(answer[4] or "") != ref.answer_sha256
            or digest(normalized_scope(json.loads(run[7]))) != ref.scope_sha256
        ):
            state = "changed"
        else:
            state = "available"
        output[ref.run_id] = state
    return output


def current_material(rows, values):
    assets = {key for value in values for key in value.asset_ids}
    assets.update(item[1] for item in rows.get("egress_asset", []))
    entries = {item[1]: item for item in rows.get("entry", [])}
    roots = [item for item in rows.get("curated_root", []) if item[3] in assets]
    ancestry = assets | {item[5] for item in roots}
    for _ in range(16):
        expanded = ancestry | {entries[key][5] for key in ancestry if key in entries and entries[key][5]}
        if expanded == ancestry:
            break
        ancestry = expanded
    tokens = {value.origin_token_id for value in values}
    tokens.update(item[1] for item in rows.get("egress_origin", []))
    tokens.update(item[5] for item in rows.get("current_result", []))
    token_rows = [item for item in rows.get("token", []) if item[1] in tokens]
    apps = {item[5] for item in token_rows if item[5]}
    app_rows = [item for item in rows.get("application", []) if item[1] in apps]
    clients = {item[3] for item in app_rows}
    thread_ids = {value.thread_id for value in values}
    selected = []
    for tag, items in rows.items():
        for item in items:
            if (
                tag
                in {
                    "deployment",
                    "membership",
                    "current_run",
                    "current_result",
                    "egress_result",
                    "egress_manifest",
                    "egress_release",
                }
                or tag.startswith("caller/")
                or tag.startswith("reader/")
                or tag == "thread"
                and item[1] in thread_ids
                or tag == "entry"
                and item[1] in ancestry
                or tag == "binding"
                and item[3] in ancestry
                or tag in {"curated_state"}
                and item[1] in assets
                or tag == "curated_root"
                and item[3] in assets
                or tag == "token"
                and item[1] in tokens
                or tag == "application"
                and item[1] in apps
                or tag == "registration"
                and item[3] in clients
            ):
                selected.append(item)
    return material_digest(selected)
