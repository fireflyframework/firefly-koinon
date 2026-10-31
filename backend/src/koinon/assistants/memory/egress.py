# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reauthorize immutable answer generations at their final transfer boundary."""

from pyfly.container import Provider, service
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.memory.egress_dtos import MemoryEgressBinding, MemoryEgressPin
from koinon.assistants.memory.egress_repository import MemoryEgressRepository
from koinon.assistants.memory.mappers import digest
from koinon.assistants.memory.projections import MemoryCurrentEvidence, MemoryCurrentResult
from koinon.assistants.memory.service import PersonalConversationMemory, unavailable
from koinon.evidence.access import EvidenceAccess
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import TransitiveSourceResolverPort


@service(name="assistants.memory_egress")
class MemoryEgress:
    def __init__(
        self,
        memory: Provider[PersonalConversationMemory],
        repository: MemoryEgressRepository,
        access: Provider[EvidenceAccess | None],
    ):
        self.memory, self.repository = memory, repository
        self.access = access

    async def bind(self, subject, tenant_id, selections):
        memory = self.memory.get()
        generations, selected = {}, {}
        for run_id, result_ids in selections:
            generation = await memory.repository.generation(run_id)
            identifiers = tuple(dict.fromkeys((*result_ids, *((generation.id,) if generation else ()))))
            generations[run_id] = generation.id if generation else None
            selected[run_id] = identifiers
        identifiers = tuple(sorted({key for ids in selected.values() for key in ids}))
        _, rows = await self.repository.fixed(subject, tenant_id, tuple(selected), identifiers)
        if {row.id for row in rows} != set(identifiers):
            raise unavailable()
        groups = {
            (run_id, generation): {generation} if generation else set()
            for run_id, generation in generations.items()
        }
        for row in rows:
            if row.kind == "generation":
                continue
            generation = row.payload.get("generation_id")
            groups.setdefault((row.run_id, generation), set()).add(row.id)
            if generation:
                groups[(row.run_id, generation)].add(generation)
        for identifier, run_id, kind, generation in await self.repository.result_ids(tuple(selected)):
            if kind != "generation" and (run_id, generation) in groups:
                groups[(run_id, generation)].add(identifier)
        if len(groups) > 200:
            raise unavailable()
        identifiers = tuple(sorted({key for ids in groups.values() for key in ids}))
        _, rows = await self.repository.fixed(subject, tenant_id, tuple(selected), identifiers)
        if {row.id for row in rows} != set(identifiers):
            raise unavailable()
        indexed = {row.id: row for row in rows}
        manifests = {
            row.generation_id: row
            for row in await self.repository.manifests(
                tuple(generation for _, generation in groups if generation)
            )
        }
        bindings = []
        for (run_id, generation_id), identifiers in groups.items():
            manifest = manifests.get(generation_id)
            results = tuple(indexed[key] for key in identifiers)
            bindings.append(
                MemoryEgressBinding(
                    run_id=run_id,
                    generation_id=generation_id,
                    manifest_sha256=manifest.manifest_sha256 if manifest else None,
                    results=tuple(
                        MemoryEgressPin(id=row.id, sha256=digest({"kind": row.kind, "payload": row.payload}))
                        for row in sorted(results, key=lambda row: row.id)
                    ),
                )
            )
        return tuple(bindings)

    async def authorize(
        self,
        subject,
        tenant_id,
        bindings,
        *,
        transfer=False,
        consent=False,
        reader_subject=None,
        captures=(),
        release_check=None,
        token_ids=(),
        release=None,
        asset_ids=(),
    ):
        if not bindings:
            return False
        if len(bindings) > 200:
            raise unavailable()
        memory = self.memory.get()
        run_ids = tuple(dict.fromkeys(item.run_id for item in bindings))
        pins = {pin.id: pin.sha256 for binding in bindings for pin in binding.results}
        if len(pins) > 2000:
            raise unavailable()
        headers, rows = await self.repository.fixed(subject, tenant_id, run_ids, tuple(pins))
        if {run.id for run, _ in headers} != set(run_ids) or {row.id for row in rows} != set(pins):
            raise unavailable()
        indexed = {row.id: row for row in rows}
        for row in rows:
            if (
                row.run_id not in run_ids
                or digest({"kind": row.kind, "payload": row.payload}) != pins[row.id]
            ):
                raise unavailable()
        values, manifests, evidence, historical = [], {}, [], set()
        captured = {
            row.generation_id: row
            for row in await self.repository.manifests(
                tuple(binding.generation_id for binding in bindings if binding.generation_id)
            )
        }
        by_run = {run.id: (run, thread) for run, thread in headers}
        for binding in bindings:
            run, thread = by_run[binding.run_id]
            own = tuple(indexed[pin.id] for pin in binding.results)
            if any(row.run_id != run.id for row in own):
                raise unavailable()
            if binding.generation_id:
                generation = indexed.get(binding.generation_id)
                if generation is None or generation.kind != "generation":
                    raise unavailable()
                row = captured.get(binding.generation_id)
                if (row.manifest_sha256 if row else None) != binding.manifest_sha256:
                    raise unavailable()
                if row:
                    value = memory.decode(row)
                    if (value.subject, value.tenant_id, value.run_id) != (subject, tenant_id, run.id):
                        raise unavailable()
                    values.append(value)
                    manifests[value.generation_id] = row.manifest_sha256
                    active = (
                        await memory.repository.generation(run.id)
                        if generation.payload.get("generation", {}).get("status") == "started"
                        else None
                    )
                    if active is None or active.id != generation.id:
                        historical.add(value.generation_id)
            scope = next((value.knowledge_scope for value in values if value.run_id == run.id), run.scope)
            assets = set(scope.get("asset_ids", []))
            assets.update(
                scope[key] for key in ("workspace_id", "project_id", "collection_id") if scope.get(key)
            )
            assets.update(key for row in own for key in row.payload.get("asset_ids", []))
            evidence.append(
                MemoryCurrentEvidence(
                    run.id,
                    thread.id,
                    subject,
                    tenant_id,
                    scope,
                    run.access_token_id,
                    tuple(
                        MemoryCurrentResult(row.id, run.id, row.kind, row.payload, row.created_at)
                        for row in own
                    ),
                    tuple(sorted(assets)),
                )
            )
        context = SecurityContextHolder.get_context()
        caller = context.attributes.get("koinon_token_id") if context else None
        reader = reader_subject or subject

        async def observe():
            return await memory.authority_repository.observe_many(
                tuple(values),
                memory.catalog.effective_membership_rows(),
                caller,
                memory.deployment_digest(),
                tuple(evidence),
                captures,
                egress_pins=pins,
                egress_manifests=manifests,
                additional_token_ids=token_ids,
                release=release,
                additional_asset_ids=asset_ids,
                **({"reader_subject": reader} if reader != subject else {}),
            )

        before = await observe()
        remembered = any(value.turns for value in values)
        if transfer and remembered and not consent:
            from pyfly.kernel import ConflictException

            raise ConflictException(
                "Review the remembered context before transferring this answer",
                code="MEMORY_TRANSFER_REVIEW_REQUIRED",
            )

        async def validate():
            if release_check is not None:
                await release_check()
            if reader != subject:
                await self.transfer_policies(subject, reader, tenant_id, values, evidence)
            else:
                await memory.validate_current(subject, tenant_id, evidence)
                for value in values:
                    if value.turns:
                        if value.generation_id in historical:
                            await memory.validate_replay(value)
                        else:
                            if before[value.generation_id].origin_sha256 != value.authority_sha256:
                                raise unavailable()
                            await memory.validate_sources(value)
                await self.owner_transitive_sources(subject, tenant_id, values, evidence)

        validated = await memory.authorize_fixed(
            subject,
            tenant_id,
            tuple(values),
            tuple(evidence),
            validate=validate,
            captures=captures,
            observation={
                "egress_pins": pins,
                "egress_manifests": manifests,
                "additional_token_ids": token_ids,
                "release": release,
                "additional_asset_ids": asset_ids,
                **({"reader_subject": reader} if reader != subject else {}),
            },
        )
        after = await observe()
        if before != validated or validated != after:
            raise unavailable()
        return remembered

    async def transfer_policies(self, owner, reader, tenant_id, values, evidence):
        from types import SimpleNamespace

        memory, access = self.memory.get(), self.access.get()
        if access is None:
            raise unavailable()
        identifiers = tuple(
            sorted({pin.id for value in values for ref in value.dependencies for pin in ref.result_pins})
        )
        rows = tuple(await memory.repository.pinned_results(identifiers))
        if {row.id for row in rows} != set(identifiers):
            raise unavailable()
        all_rows = (*rows, *(row for current in evidence for row in current.results))
        sources = tuple(
            {
                source["id"]: SourceReference.model_validate(source)
                for row in all_rows
                for source in row.payload.get("source_manifest", {}).get("sources", [])
            }.values()
        )
        tokens = {value.origin_token_id for value in values}
        tokens.update(ref.origin_token_id for value in values for ref in value.dependencies)
        tokens.update(current.origin_token_id for current in evidence)
        await access.check(
            reader,
            tenant_id,
            sources,
            permission="shares:read",
            owner_subject=owner,
            originating_token_ids=tuple(sorted(tokens - {None})),
        )
        for value in values:
            for ref in value.dependencies:
                own = tuple(row for row in rows if row.id in {pin.id for pin in ref.result_pins})
                if any(
                    digest({"kind": row.kind, "payload": row.payload})
                    != next(pin.sha256 for pin in ref.result_pins if pin.id == row.id)
                    for row in own
                ):
                    raise unavailable()
                origin = SimpleNamespace(access_token_id=ref.origin_token_id, scope=value.knowledge_scope)
                await self.origin_sources(owner, reader, tenant_id, origin, own)
        for current in evidence:
            origin = SimpleNamespace(access_token_id=current.origin_token_id, scope=current.scope)
            await self.origin_sources(owner, reader, tenant_id, origin, current.results)
        assets = {key for value in (*values, *evidence) for key in value.asset_ids}
        for asset in assets:
            entry = await memory.catalog.get(reader, tenant_id, asset)
            await memory.catalog.authorize(reader, tenant_id, "shares:read", entry.workspace_id)
        if sources:
            resolver = memory.sources.get()
            if resolver is None:
                raise unavailable()
            verified = await resolver.resolve(reader, tenant_id, sources)
            if {item.id for item in verified} != {item.id for item in sources} or any(
                item.availability == "unverified" for item in verified
            ):
                raise unavailable()

    async def origin_sources(self, owner, reader, tenant_id, origin, rows):
        from types import SimpleNamespace

        memory = self.memory.get()
        references = tuple(
            {
                source["id"]: SourceReference.model_validate(source)
                for row in rows
                for source in row.payload.get("source_manifest", {}).get("sources", [])
            }.values()
        )
        if any(source.kind == "knowledge_version" for source in references):
            resolver = memory.sources.get()
            if not isinstance(resolver, TransitiveSourceResolverPort):
                raise unavailable()
            roots = await resolver.resolve_bounds(reader, tenant_id, references)
            scope = {
                **origin.scope,
                "asset_ids": sorted(
                    {*origin.scope.get("asset_ids", []), *(source.asset_id for source in roots)}
                ),
            }
            origin = SimpleNamespace(access_token_id=origin.access_token_id, scope=scope)
        await memory.assistants.get().origin_authority(owner, tenant_id, origin, rows)

    async def owner_transitive_sources(self, subject, tenant_id, values, evidence):
        from types import SimpleNamespace

        memory = self.memory.get()
        identifiers = tuple(
            sorted({pin.id for value in values for ref in value.dependencies for pin in ref.result_pins})
        )
        rows = tuple(await memory.repository.pinned_results(identifiers))
        for value in values:
            for ref in value.dependencies:
                own = tuple(row for row in rows if row.id in {pin.id for pin in ref.result_pins})
                if any(
                    source.get("kind") == "knowledge_version"
                    for row in own
                    for source in row.payload.get("source_manifest", {}).get("sources", [])
                ):
                    await self.origin_sources(
                        subject,
                        subject,
                        tenant_id,
                        SimpleNamespace(access_token_id=ref.origin_token_id, scope=value.knowledge_scope),
                        own,
                    )
        for current in evidence:
            if any(
                source.get("kind") == "knowledge_version"
                for row in current.results
                for source in row.payload.get("source_manifest", {}).get("sources", [])
            ):
                await self.origin_sources(
                    subject,
                    subject,
                    tenant_id,
                    SimpleNamespace(access_token_id=current.origin_token_id, scope=current.scope),
                    current.results,
                )

    async def query(self, subject, tenant_id, query_id):
        rows = await self.repository.query_results(tenant_id, query_id)
        by_run = {}
        for result, owner in rows:
            if owner != subject:
                raise unavailable()
            by_run.setdefault(result.run_id, []).append(result)
        memory = self.memory.get()
        bindings = []
        manifests = {
            row.generation_id: row
            for row in await self.repository.manifests(
                tuple(
                    {row.payload.get("generation_id") for results in by_run.values() for row in results}
                    - {None}
                )
            )
        }
        for run_id, results in by_run.items():
            generations = {row.payload.get("generation_id") for row in results}
            for generation_id in generations:
                own = [row for row in results if row.payload.get("generation_id") == generation_id]
                manifest = manifests.get(generation_id)
                if generation_id:
                    generation = await memory.assistants.get().results.find_by_id(generation_id)
                    if generation is None:
                        raise unavailable()
                    own.append(generation)
                bindings.append(
                    MemoryEgressBinding(
                        run_id=run_id,
                        generation_id=generation_id,
                        manifest_sha256=manifest.manifest_sha256 if manifest else None,
                        results=tuple(
                            MemoryEgressPin(
                                id=row.id, sha256=digest({"kind": row.kind, "payload": row.payload})
                            )
                            for row in own
                        ),
                    )
                )
        await self.authorize(subject, tenant_id, tuple(bindings))

    async def remembered_sources(self, subject, tenant_id, bindings):
        memory = self.memory.get()
        sources = {}
        captured = {
            row.generation_id: row
            for row in await self.repository.manifests(
                tuple(binding.generation_id for binding in bindings if binding.generation_id)
            )
        }
        for binding in bindings:
            if not binding.generation_id:
                continue
            row = captured.get(binding.generation_id)
            if (row.manifest_sha256 if row else None) != binding.manifest_sha256:
                raise unavailable()
            if row is None:
                continue
            value = memory.decode(row)
            identifiers = tuple(sorted({pin.id for ref in value.dependencies for pin in ref.result_pins}))
            rows = await memory.repository.pinned_results(identifiers)
            for result in rows:
                for source in result.payload.get("source_manifest", {}).get("sources", []):
                    sources[source["id"]] = SourceReference.model_validate(source)
                    if len(sources) > 500:
                        raise unavailable()
        await self.authorize(subject, tenant_id, bindings)
        return tuple(sources[key] for key in sorted(sources))
