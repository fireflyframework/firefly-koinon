# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader cancellation cannot outlive the native operation using its paths."""

import asyncio
import contextvars
import threading

import pytest


@pytest.mark.parametrize("operation", ["enumerate", "materialise"])
async def test_reader_cancellation_waits_for_native_path_use(monkeypatch, tmp_path, operation):
    from flyquery.core.services.ingestion.reader import TableExtractionRules
    from flyquery.core.services.ingestion.reader_factory import get_reader

    source = tmp_path / "orders.json"
    source.write_text('[{"item": "A", "amount": 47}]')
    target = tmp_path / "orders.parquet"
    reader = get_reader("json")
    rules = TableExtractionRules()
    table = (await reader.enumerate_tables(str(source), rules))[0]
    started = asyncio.Event()
    release = threading.Event()
    finished = threading.Event()
    loop = asyncio.get_running_loop()
    name = "_enumerate_sync" if operation == "enumerate" else "_materialise_sync"
    original = getattr(reader, name)

    def blocked(*args):
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise RuntimeError("test did not release native reader")
        try:
            assert source.exists()
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(reader, name, blocked)
    if operation == "enumerate":
        pending = reader.enumerate_tables(str(source), rules)
    else:
        pending = reader.materialise(
            str(source), table, str(target), workspace_locale="en-US", type_infer_sample_rows=10
        )
    task = asyncio.create_task(pending)
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel("original cancellation")
        await asyncio.sleep(0)
        task.cancel("repeated cancellation")
        await asyncio.sleep(0)
        assert not task.done(), "reader returned while native code still owned its input/output paths"
        assert not finished.is_set()
    finally:
        release.set()
        result = (await asyncio.gather(task, return_exceptions=True))[0]
        assert await asyncio.to_thread(finished.wait, 2)
    assert isinstance(result, asyncio.CancelledError)
    assert finished.is_set()
    assert source.read_text() == '[{"item": "A", "amount": 47}]'
    if operation == "materialise":
        import pyarrow.parquet as pq

        assert pq.read_table(target).to_pylist() == [{"item": "A", "amount": 47}]


@pytest.mark.parametrize("failure", [None, ValueError, asyncio.CancelledError])
async def test_native_call_preserves_context_and_result_or_error(failure):
    from flyquery.core.services.ingestion.native_call import run_native

    trace = contextvars.ContextVar("reader_trace", default="missing")
    token = trace.set("request-trace")
    error = failure("native reader failure") if failure else None
    caller_thread = threading.get_ident()

    def native(value, *, amount):
        assert threading.get_ident() != caller_thread
        assert trace.get() == "request-trace"
        trace.set("native-only")
        if failure:
            raise error
        return value + amount

    try:
        if failure:
            with pytest.raises(failure) as caught:
                await run_native(native, 3, amount=4)
            assert caught.value is error
            assert caught.value.__cause__ is None
        else:
            assert await run_native(native, 3, amount=4) == 7
        assert trace.get() == "request-trace"
    finally:
        trace.reset(token)


@pytest.mark.parametrize("failure", [False, True])
async def test_native_call_repeated_cancel_waits_and_preserves_original_cancellation(failure):
    from flyquery.core.services.ingestion.native_call import run_native

    started = asyncio.Event()
    release = threading.Event()
    finished = threading.Event()
    loop = asyncio.get_running_loop()

    def native():
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise RuntimeError("test did not release native call")
        finished.set()
        if failure:
            raise ValueError("failure after cancellation")
        return "native result"

    task = asyncio.create_task(run_native(native))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel("original cancellation")
        await asyncio.sleep(0)
        task.cancel("repeated cancellation")
        await asyncio.sleep(0)
        assert not task.done()
        assert not finished.is_set()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await task
    assert str(caught.value) == "original cancellation"
    assert finished.is_set()
    if failure:
        assert isinstance(caught.value.__cause__, ValueError)


def test_asyncio_run_shutdown_waits_for_native_call_before_caller_cleanup():
    from flyquery.core.services.ingestion.native_call import run_native

    started = threading.Event()
    main_returning = threading.Event()
    release = threading.Event()
    native_finished = threading.Event()
    caller_finished = threading.Event()
    errors = []

    def native():
        started.set()
        if not release.wait(5):
            raise RuntimeError("test did not release shutdown native call")
        native_finished.set()

    async def caller():
        try:
            await run_native(native)
        finally:
            if not native_finished.is_set():
                errors.append("caller cleanup ran before native call finished")
            caller_finished.set()

    async def main():
        task = asyncio.create_task(caller())
        while not started.is_set():
            if task.done():
                await task
            await asyncio.sleep(0)
        main_returning.set()
        return task

    def run():
        try:
            asyncio.run(main())
        except BaseException as error:
            errors.append(error)

    runner = threading.Thread(target=run)
    runner.start()
    try:
        assert main_returning.wait(2)
        assert not caller_finished.wait(0.05)
        assert runner.is_alive()
    finally:
        release.set()
        runner.join(timeout=3)
    assert not runner.is_alive()
    assert native_finished.is_set()
    assert caller_finished.is_set()
    assert errors == []
