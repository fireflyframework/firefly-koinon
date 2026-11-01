# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-owned ingestion budgets, independent of query-execution settings."""

from __future__ import annotations

import contextvars
import re
import tempfile
import threading
from collections.abc import Callable, Coroutine
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, overload


class IngestionResourceLimitError(ValueError):
    code = "INGEST_RESOURCE_LIMIT"


@dataclass(frozen=True)
class IngestionResourcePolicy:
    memory_limit: str = "512MiB"
    threads: int = 1
    scratch_max_bytes: int = 8 * 1024 * 1024 * 1024
    decompressed_max_bytes: int = 5 * 1024 * 1024 * 1024
    native_connections: int = 32
    scratch_root: str | None = None
    reader_rss_max_bytes: int = 768 * 1024**2
    reader_timeout_seconds: int = 120
    excel_max_cells: int = 2_000_000
    excel_max_rows: int = 1_000_000
    excel_max_columns: int = 4096
    shared_strings_max_bytes: int = 32 * 1024**2

    def __post_init__(self):
        if not isinstance(self.memory_limit, str) or not re.fullmatch(
            r"[1-9][0-9]{0,5}(?:KiB|MiB|GiB|KB|MB|GB)", self.memory_limit
        ):
            raise ValueError("Ingestion memory must be an explicit bounded byte-unit value")
        match = re.fullmatch(r"([1-9][0-9]{0,5})(KiB|MiB|GiB|KB|MB|GB)", self.memory_limit)
        assert match is not None
        units = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "KB": 1000, "MB": 1000**2, "GB": 1000**3}
        if int(match[1]) * units[match[2]] > 64 * 1024**3:
            raise ValueError("Ingestion memory cannot exceed 64 GiB per native connection")
        for value, maximum in (
            (self.reader_rss_max_bytes, 8 * 1024**3),
            (self.reader_timeout_seconds, 120),
            (self.excel_max_cells, 16_000_000),
            (self.excel_max_rows, 1_048_576),
            (self.excel_max_columns, 16_384),
            (self.shared_strings_max_bytes, 256 * 1024**2),
            (self.threads, 64),
            (self.native_connections, 32),
            (self.scratch_max_bytes, 64 * 1024**3),
            (self.decompressed_max_bytes, 64 * 1024**3),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Ingestion resources exceed their configured bounds")
        if self.decompressed_max_bytes > self.scratch_max_bytes:
            raise ValueError("Decompression cannot exceed the ingestion scratch budget")
        if self.scratch_root is not None:
            path = Path(self.scratch_root)
            if not path.is_absolute() or path != path.resolve() or not path.is_dir():
                raise ValueError("Ingestion scratch root must be an existing canonical directory")

    @classmethod
    def from_settings(cls, settings: Any):
        defaults = cls()
        return cls(
            **{
                field: getattr(settings, "ingest_" + field, getattr(defaults, field))
                for field in (
                    "scratch_max_bytes",
                    "decompressed_max_bytes",
                    "native_connections",
                    "scratch_root",
                    "reader_rss_max_bytes",
                    "reader_timeout_seconds",
                    "excel_max_cells",
                    "excel_max_rows",
                    "excel_max_columns",
                    "shared_strings_max_bytes",
                )
            },
            memory_limit=getattr(settings, "ingest_duckdb_memory_limit", defaults.memory_limit),
            threads=getattr(settings, "ingest_duckdb_threads", defaults.threads),
        )


def directory_files(root: Path):
    count = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise IngestionResourceLimitError("Owned scratch contains an unexpected symbolic link")
        try:
            if path.is_file():
                count += 1
                if count > 4096:
                    raise IngestionResourceLimitError("Owned scratch exceeds its file-count budget")
                yield path.resolve(), path.stat().st_size
        except FileNotFoundError:
            continue


def directory_bytes(root: Path) -> int:
    return sum(size for _, size in directory_files(root))


@dataclass
class _ChildBudget:
    scope: Any
    token: object
    maximum: int
    reserved: int

    def publish(self, source: Path, destination: Path, size: int) -> None:
        if size > self.reserved or size < 0:
            raise IngestionResourceLimitError("Parser output exceeds its reserved scratch budget")
        with self.scope.lock:
            self.scope.check()
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.chmod(0o600)
            source.replace(destination)
            self.scope.reservations[self.token] = self.reserved - size
            self.scope.paths[destination.resolve()] = size
            self.scope.check()


class _Scope:
    def __init__(self, policy: IngestionResourcePolicy):
        self.policy = policy
        self.paths: dict[Path, int] = {}
        self.pending: set[Path] = set()
        self.directories: set[Path] = set()
        self.reservations: dict[object, int] = {}
        self.lock = threading.RLock()

    def usage(self) -> int:
        with self.lock:
            values = {}
            for path, reserved in self.paths.items():
                try:
                    size = path.stat().st_size
                    self.pending.discard(path)
                except FileNotFoundError:
                    if path not in self.pending:
                        continue
                    size = 0
                values[path] = max(reserved, size)
            for directory in self.directories:
                for path, size in directory_files(directory):
                    values[path] = max(values.get(path, 0), size)
            return sum(values.values()) + sum(self.reservations.values())

    def account(self, path: str | Path, reserved: int | None = None) -> None:
        target = Path(path).resolve()
        with self.lock:
            old = self.paths.get(target, 0)
            self.paths[target] = old if reserved is None else reserved
            if reserved is not None and not target.exists():
                self.pending.add(target)
            if self.usage() > self.policy.scratch_max_bytes:
                self.paths[target] = old
                raise IngestionResourceLimitError("Ingestion scratch exceeds its configured byte budget")

    def owned_directory(self, root: str | Path) -> None:
        with self.lock:
            self.directories.add(Path(root).resolve())
            self.check()

    @contextmanager
    def child_budget(self, source: str | Path):
        source = Path(source).resolve()
        token = object()
        with self.lock:
            self.account(source)
            remaining = self.policy.scratch_max_bytes - self.usage()
            if remaining <= 0:
                raise IngestionResourceLimitError("Ingestion scratch has no remaining parser capacity")
            self.reservations[token] = remaining
            allocation = _ChildBudget(self, token, remaining + source.stat().st_size, remaining)
        try:
            yield allocation
        finally:
            with self.lock:
                self.reservations.pop(token, None)

    def check(self) -> None:
        with self.lock:
            if self.usage() > self.policy.scratch_max_bytes:
                raise IngestionResourceLimitError("Ingestion scratch exceeds its configured byte budget")


_scope: contextvars.ContextVar[_Scope | None] = contextvars.ContextVar("ingestion_resources", default=None)
_native_lock = threading.Lock()
_native_active = 0
_native_limits: list[int] = []


def current_scope() -> _Scope:
    return _scope.get() or _Scope(IngestionResourcePolicy())


@contextmanager
def resource_scope(settings: Any):
    current = _scope.get()
    if current is not None:
        yield current
        return
    scope = _Scope(IngestionResourcePolicy.from_settings(settings))
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


@overload
def ingestion_resources[**P, T](
    function: Callable[P, Coroutine[Any, Any, T]],
    *,
    settings: None = None,
) -> Callable[P, Coroutine[Any, Any, T]]: ...


@overload
def ingestion_resources[**P, T](
    function: None = None,
    *,
    settings: Callable[[Any], Any],
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]: ...


def ingestion_resources(function: Any = None, *, settings: Any = None) -> Any:
    def decorate(target):
        @wraps(target)
        async def bounded(*args, **kwargs):
            configured = settings(args[0]) if settings is not None else kwargs.get("settings")
            with resource_scope(configured):
                for name in ("local_temp_path", "parquet_key"):
                    path = kwargs.get(name)
                    if path and Path(path).is_file():
                        account_path(path)
                return await target(*args, **kwargs)

        return bounded

    return decorate(function) if function is not None else decorate


def account_path(path: str | Path) -> None:
    current_scope().account(path)


def bounded_copy(source, target, cap: int) -> None:
    scope = current_scope()
    total = 0
    while chunk := source.read(64 * 1024):
        total += len(chunk)
        if total > cap:
            raise IngestionResourceLimitError(f"decompressed size exceeded cap ({cap} bytes)")
        scope.account(target.name, total)
        target.write(chunk)


def write_bytes(path: str | Path, content: bytes) -> None:
    scope = current_scope()
    scope.account(path, len(content))
    with open(path, "wb") as target:
        scope.account(path, len(content))
        target.write(content)


def output_size(path: str | Path) -> int:
    account_path(path)
    return Path(path).stat().st_size


def copy_file(source: str | Path, target: str | Path) -> None:
    with open(source, "rb") as incoming, open(target, "wb") as outgoing:
        bounded_copy(incoming, outgoing, current_scope().policy.scratch_max_bytes)


class BoundedTextWriter:
    def __init__(self, stream):
        self.stream, self.size = stream, 0

    def write(self, value: str):
        self.size += len(value.encode("utf-8"))
        current_scope().account(self.stream.name, self.size)
        return self.stream.write(value)


class _Connection:
    def __init__(self, native, directory, scope: _Scope):
        self.native, self.directory, self.scope = native, directory, scope
        self.closed = False

    def _call(self, function, *args, **kwargs) -> Any:
        import duckdb

        try:
            result = function(*args, **kwargs)
        except (duckdb.OutOfMemoryException, MemoryError) as error:
            raise IngestionResourceLimitError("Ingestion exceeds configured native resources") from error
        except duckdb.IOException as error:
            if any(
                part in str(error).lower() for part in ("max_temp_directory_size", "no space left", "offload")
            ):
                raise IngestionResourceLimitError("Ingestion exceeds configured scratch resources") from error
            raise
        self.scope.check()
        return result

    def execute(self, *args, **kwargs) -> _Connection:
        self._call(self.native.execute, *args, **kwargs)
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._call(self.native.fetchone)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._call(self.native.fetchall)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.native, name)

    def close(self):
        global _native_active
        if not self.closed:
            self.closed = True
            try:
                self.native.close()
            finally:
                try:
                    self.directory.cleanup()
                finally:
                    with _native_lock:
                        _native_active -= 1
                        _native_limits.remove(self.scope.policy.native_connections)


def connect():
    import duckdb

    global _native_active
    scope = current_scope()
    policy = scope.policy
    with _native_lock:
        if _native_active >= min([policy.native_connections, *_native_limits]):
            raise IngestionResourceLimitError("Ingestion native connection capacity is full")
        _native_active += 1
        _native_limits.append(policy.native_connections)
    directory = None
    try:
        scope.check()
        remaining = policy.scratch_max_bytes - scope.usage()
        if remaining < policy.native_connections:
            raise IngestionResourceLimitError("Ingestion scratch capacity is full")
        directory = tempfile.TemporaryDirectory(prefix="flyquery-ingest-", dir=policy.scratch_root)
        scope.owned_directory(directory.name)
        native = duckdb.connect(
            config={
                "memory_limit": policy.memory_limit,
                "threads": str(policy.threads),
                "temp_directory": directory.name,
                "max_temp_directory_size": str(remaining // policy.native_connections) + "B",
            }
        )
        return _Connection(native, directory, scope)
    except BaseException:
        if directory is not None:
            directory.cleanup()
        with _native_lock:
            _native_active -= 1
            _native_limits.remove(policy.native_connections)
        raise
