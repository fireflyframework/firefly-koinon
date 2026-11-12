# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operation-owned preferences and fresh exact-origin consumption fences."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace

from pyfly.container import Provider, service
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate

from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.read_authority import SourceReadAuthority
from koinon.integrations.content_sources.read_dtos import (
    LocalFolderSourcePin,
    LocalSourcePin,
    ReaderSelectionSnapshot,
    ReaderSourceSelection,
)
from koinon.integrations.content_sources.read_native import SourceReadNative
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections
from koinon.security.authority import PRIMARY_POLICY_UNIT, primary_authority


@dataclass
class SourceReadOperation:
    actor: str
    tenant: str
    selection: ReaderSelectionSnapshot
    reader: "SourceReader"
    used: set[LocalSourcePin | LocalFolderSourcePin] = field(default_factory=set)
    _comparisons: list = field(default_factory=list, repr=False)
    _examined: set[LocalSourcePin | LocalFolderSourcePin] = field(default_factory=set, repr=False)
    _checked: set[LocalSourcePin | LocalFolderSourcePin] = field(default_factory=set, repr=False)
    _archived_target: str | None = field(default=None, repr=False)
    _owner_task: object = field(default_factory=asyncio.current_task, repr=False)
    _entry_states: dict[tuple[str, ...], tuple] = field(default_factory=dict, repr=False)

    def _remember_entries(self, identifiers, state):
        previous = self._entry_states.setdefault(identifiers, state)
        if len({value for key in self._entry_states for value in key}) > 1000:
            raise SourceError("size_exceeded")
        if previous != state:
            raise SourceError("authority_changed")

    async def _confirm_entries(self):
        if not self._entry_states:
            return
        identifiers = tuple(dict.fromkeys(value for key in self._entry_states for value in key))
        expected = {}
        for state in self._entry_states.values():
            for row in state:
                if expected.setdefault(row.id, row) != row:
                    raise SourceError("authority_changed")
        if await self.reader.records.entry_read_state(self.tenant, identifiers) != tuple(
            expected[key] for key in sorted(expected)
        ):
            raise SourceError("authority_changed")
        for identifier in identifiers:
            await self.reader.authority.catalog.get_identity(self.actor, self.tenant, identifier)

    def validate_result(self, result):
        snapshots = {
            pin.version_id
            for pin in self.used
            if isinstance(pin, LocalSourcePin)
            and pin.domain == "structured"
            and pin.asset_id == result.asset_id
        }
        if snapshots and (not result.snapshot_manifest_complete or set(result.snapshot_ids) != snapshots):
            raise SourceError("version_changed")

    async def check(self, pins, *, remember=True):
        pins = tuple(pins)
        try:
            self._examined.update(pins)
            if len(self._examined) > 1000:
                raise SourceError("size_exceeded")
            await self.reader.selections.confirm(self.actor, self.tenant, self.selection)
            options = {"archived_target": self._archived_target} if self._archived_target else {}
            comparison = await self.reader.authority._check(
                self.actor, self.tenant, pins, self.selection.connections, **options
            )
            await self.reader.selections.confirm(self.actor, self.tenant, self.selection)
        except BaseException:
            self._comparisons.clear()
            self._checked.clear()
            raise
        if remember:
            self.used.update(pins)
            self._checked.update(pins)
            self._comparisons.append(comparison)

    async def release(self):
        if self._entry_states:
            async with primary_authority(fresh=True):
                await self._confirm_entries()
        self._comparisons.clear()
        self._checked.clear()
        pins = tuple(self.used)
        for start in range(0, len(pins), 1000):
            await self.check(pins[start : start + 1000])
        await self.reader.selections.confirm(self.actor, self.tenant, self.selection)

    @asynccontextmanager
    async def read_fence(self):
        """Use one read-only local snapshot after fresh external authorization."""
        _no_remote_unit()
        if asyncio.current_task() is not self._owner_task:
            raise SourceError("authority_changed")
        comparisons, self._comparisons = tuple(self._comparisons), []
        checked, self._checked = self._checked, set()
        if self.used and (not comparisons or not self.used <= checked):
            raise SourceError("authority_changed")
        async with TransactionTemplate(
            "primary",
            name=PRIMARY_POLICY_UNIT,
            propagation=Propagation.REQUIRED,
            isolation=Isolation.SERIALIZABLE,
            read_only=True,
            read_from_primary=True,
        ).transaction():
            await self.reader.selections.confirm_local(self.actor, self.tenant, self.selection)
            await self._confirm_entries()
            for comparison in comparisons:
                await self.reader.authority._compare(self.actor, self.tenant, comparison)
            yield

    @asynccontextmanager
    async def local_fence(self):
        """Commit local writes under the same operation's fresh checks, consuming them once."""
        _no_remote_unit()
        if asyncio.current_task() is not self._owner_task:
            raise SourceError("authority_changed")
        comparisons, self._comparisons = tuple(self._comparisons), []
        checked, self._checked = self._checked, set()
        if self.used and (not comparisons or not self.used <= checked):
            raise SourceError("authority_changed")
        async with primary_authority(read_only=False):
            await self.reader.authority.catalog._lock_tenant(self.tenant)
            await self.reader.selections.lock_confirm(self.actor, self.tenant, self.selection)
            await self._confirm_entries()
            await self.reader.authority._lock_comparisons(self.actor, self.tenant, comparisons)
            yield

    def bind_receipt(self, receipt):
        receipt.requires_source_authority = True

        async def authorize(native_pins, scope, *, remember=True):
            canonical = []
            for pin in native_pins:
                asset = receipt.canonical_documents.get((scope.workspace_id, pin.source_id))
                if asset is None:
                    raise SourceError("access_denied")
                canonical.append(
                    LocalSourcePin(
                        asset,
                        "canon",
                        scope.workspace_id,
                        pin.source_id,
                        pin.source_version_id or "",
                        pin.extraction_id,
                        pin.source_part_id,
                    )
                )
            await self.check(tuple(canonical), remember=remember)

        async def admit(native_pins, scope):
            groups = {}
            for pin in native_pins:
                groups.setdefault((pin.source_id, pin.source_version_id, pin.extraction_id), []).append(pin)
            admitted = []
            for values in groups.values():
                try:
                    await authorize(tuple(values), scope, remember=False)
                except SourceError as error:
                    if error.code == "size_exceeded":
                        raise
                    continue
                except AccessDenied:
                    continue
                admitted.extend(values)
            selected = set(admitted)
            return tuple(pin for pin in native_pins if pin in selected)

        receipt.source_candidate_admission = admit
        receipt.source_pin_authorization = authorize


@service(name="content_sources.reader")
class SourceReader:
    def __init__(
        self,
        authority: SourceReadAuthority,
        selections: SourceReaderSelections,
        records: SourceReadRepository,
        native: Provider[SourceReadNative | None] | None = None,
    ):
        self.authority, self.selections, self.records = authority, selections, records
        self.native = native

    @asynccontextmanager
    async def mutation(self, actor, tenant, identifiers, *, action, target):
        if not identifiers:
            yield
            return
        async with primary_authority(fresh=True):
            descendants = await self.records.mutation_entries(tenant, (target,)) if target else ()
            candidates = tuple(dict.fromkeys((*identifiers, *descendants)))
            pins = await self.records.entry_pins(tenant, candidates)
            curated = await self.records.curated_entry_references(tenant, candidates)
        if not pins and not curated:
            yield
            return
        operation = await self.begin(actor, tenant)
        operation._archived_target = target if action == "restore" else None
        await operation.check(pins)
        await self.sources(actor, tenant, curated, operation=operation)
        await operation.release()
        async with operation.local_fence():
            yield
        if action != "delete":
            operation._archived_target = target if action == "archive" else None
            await operation.release()

    async def sources(self, actor, tenant, sources, *, operation=None):
        """Resolve immutable manifest references without hydrating retained text or titles."""
        _no_remote_unit()
        if operation is not None and (
            operation.actor != actor
            or operation.tenant != tenant
            or operation.reader is not self
            or operation._owner_task is not asyncio.current_task()
        ):
            raise SourceError("authority_changed")
        pending, seen, pins = list(sources), set(), []
        native = self.native.get() if self.native is not None else None
        while pending:
            reference = pending.pop()
            if reference.kind not in ("document", "dataset", "knowledge_version") or not reference.asset_id:
                raise SourceError("unavailable")
            identity = (
                reference.asset_id,
                reference.kind,
                reference.knowledge_version_id,
                reference.source_version_id,
                reference.snapshot_id,
                reference.query_id,
            )
            if identity in seen:
                continue
            seen.add(identity)
            if len(seen) > 500:
                raise SourceError("size_exceeded")
            async with primary_authority(fresh=True):
                identifiers = (reference.asset_id,)
                state = await self.records.entry_read_state(tenant, identifiers)
                pins.extend(await self.records.folder_pins(tenant, identifiers))
                binding, imported = await self.records.reference_context(tenant, reference)
            operation = operation or await self.begin(actor, tenant)
            operation._remember_entries(identifiers, state)
            if reference.kind == "knowledge_version":
                if imported:
                    if native is None:
                        raise SourceError("unavailable")
                    roots = await native.curated_sources(
                        actor,
                        tenant,
                        binding.native_workspace_id,
                        reference.asset_id,
                        reference.knowledge_version_id,
                    )
                    if {root.asset_id for root in roots} != imported:
                        raise SourceError("unavailable")
                    pending.extend(roots)
                continue
            if not imported:
                continue
            snapshots = ()
            if reference.kind == "dataset":
                if reference.query_id:
                    if native is None:
                        raise SourceError("unavailable")
                    snapshots = await native.query_snapshots(actor, tenant, binding, reference.query_id)
                    if reference.snapshot_id and reference.snapshot_id not in snapshots:
                        raise SourceError("access_denied")
                elif reference.snapshot_id:
                    snapshots = (reference.snapshot_id,)
            async with primary_authority(fresh=True):
                pins.extend(await self.records.reference_pins(tenant, reference, binding, snapshots))
        if pins:
            operation = operation or await self.begin(actor, tenant)
            await operation.check(tuple(pins))
        return operation

    async def memory(self, actor, tenant, bindings, *, operation=None, owner=None):
        async with primary_authority(fresh=True):
            sources = await self.records.memory_references(tenant, bindings, owner or actor)
        return await self.sources(actor, tenant, sources, operation=operation)

    async def runs(self, actor, tenant, identifiers, *, operation=None, owner=None):
        _no_remote_unit()
        async with primary_authority(fresh=True):
            sources, bindings = await self.records.run_references(tenant, tuple(identifiers), owner or actor)
        operation = await self.sources(actor, tenant, sources, operation=operation)
        return await self.memory(actor, tenant, bindings, operation=operation, owner=owner or actor)

    async def review(self, actor, tenant, identifier, *, operation=None, owner=None):
        from koinon.assistants.memory.egress_dtos import MemoryEgressBinding

        _no_remote_unit()
        async with primary_authority(fresh=True):
            sources, values = await self.records.review_references(tenant, identifier, owner or actor)
        operation = await self.sources(actor, tenant, sources, operation=operation)
        bindings = tuple(MemoryEgressBinding.model_validate(value) for value in values)
        return await self.memory(actor, tenant, bindings, operation=operation, owner=owner or actor)

    async def curated_version(self, actor, tenant, identifier, version=None):
        from types import SimpleNamespace

        async with primary_authority(fresh=True):
            state = await self.records.curated_state(tenant, identifier)
        selected = version if version is not None else state.serving_version or state.head_version
        native = self.native.get() if self.native is not None else None
        if native is None:
            raise SourceError("unavailable")
        version_id = await native.curated_version(actor, tenant, state, selected)
        return await self.sources(
            actor,
            tenant,
            (
                SimpleNamespace(
                    asset_id=identifier,
                    kind="knowledge_version",
                    knowledge_version_id=version_id,
                    source_version_id=None,
                    snapshot_id=None,
                    query_id=None,
                ),
            ),
        )

    @asynccontextmanager
    async def curated_read(self, actor, tenant, selections):
        from types import SimpleNamespace

        from koinon.integrations.content_sources.read_capabilities import CuratedIdentity, curated_capability

        _no_remote_unit()
        if len(selections) > 128:
            raise SourceError("size_exceeded")
        operation = await self.begin(actor, tenant)
        native = self.native.get() if self.native is not None else None
        if native is None:
            raise SourceError("unavailable")
        identities, references = [], []
        for item, version in selections:
            async with primary_authority(fresh=True):
                state = await self.records.curated_state(tenant, item)
            selected = version if version is not None else state.serving_version or state.head_version
            version_id = await native.curated_version(actor, tenant, state, selected)
            identities.append(
                CuratedIdentity(
                    item,
                    state.native_workspace_id,
                    state.native_item_id,
                    version_id,
                    selected,
                    state.workspace_id,
                )
            )
            references.append(
                SimpleNamespace(
                    asset_id=item,
                    kind="knowledge_version",
                    knowledge_version_id=version_id,
                    source_version_id=None,
                    snapshot_id=None,
                    query_id=None,
                )
            )
        await self.sources(actor, tenant, references, operation=operation)
        await operation.release()
        async with operation.read_fence():
            with curated_capability(actor, tenant, identities):
                yield
        await operation.release()

    async def begin(self, actor, tenant, overrides=None):
        from koinon.integrations.content_sources.read_context import (
            current_reader_choices,
            current_reader_snapshot,
        )

        if overrides is None:
            overrides = current_reader_choices(actor, tenant)
        choices = (
            None
            if overrides is None
            else tuple(ReaderSourceSelection.model_validate(value) for value in overrides)
        )
        selection = current_reader_snapshot(actor, tenant, choices)
        if selection is None:
            selection = await self.selections.resolve(actor, tenant, choices)
        await self.selections.confirm(actor, tenant, selection)
        return SourceReadOperation(actor, tenant, selection, self)

    async def entries(
        self, actor, tenant, identifiers, *, version_id=None, extraction_id=None, part_id=None, operation=None
    ):
        if operation is not None and (
            operation.actor != actor
            or operation.tenant != tenant
            or operation.reader is not self
            or operation._owner_task is not asyncio.current_task()
        ):
            raise SourceError("authority_changed")
        identifiers = tuple(dict.fromkeys(identifiers))
        async with primary_authority(fresh=True):
            pins = await self.records.entry_pins(tenant, identifiers, version_id=version_id)
            curated = await self.records.curated_entry_references(tenant, identifiers)
            state = await self.records.entry_read_state(tenant, identifiers)
        if curated:
            operation = await self.sources(actor, tenant, curated, operation=operation)
        if extraction_id is not None:
            pins = tuple(
                replace(pin, extraction_id=extraction_id, part_id=part_id)
                if isinstance(pin, LocalSourcePin)
                else pin
                for pin in pins
            )
        operation = operation or await self.begin(actor, tenant)
        if pins:
            await operation.check(pins)
        operation._remember_entries(identifiers, state)
        return operation

    async def search_assets(self, actor, tenant, *, asset_ids=None, operation, **scope):
        """Admit canonical identities before search loads catalog titles or native content."""
        async with primary_authority(fresh=True):
            identifiers = (
                tuple(asset_ids)
                if asset_ids is not None
                else await self.records.search_candidates(tenant, **scope)
            )
        admitted = []
        for identifier in identifiers:
            try:
                async with primary_authority(fresh=True):
                    identity = await self.authority.catalog.get_identity(actor, tenant, identifier)
                if asset_ids is None and (
                    identity.status == "archived"
                    or identity.kind == "document"
                    and identity.status != "ready"
                ):
                    continue
                await self.entries(actor, tenant, (identifier,), operation=operation)
            except SourceError as error:
                if asset_ids is not None or error.code == "size_exceeded":
                    raise
                continue
            except AccessDenied:
                if asset_ids is not None:
                    raise
                continue
            admitted.append(identifier)
        return admitted
