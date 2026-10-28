# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon_sdk import Page, cursor_pages, offset_pages


async def test_offset_pages_lazy_and_items_only_once():
    calls = []

    async def fetch(number):
        calls.append(number)
        return Page[int](items=[number], page=number, pages=3)

    pages = offset_pages(fetch)
    assert calls == []
    assert (await anext(pages)).items == [1]
    assert calls == [1]
    await pages.aclose()
    assert calls == [1]

    async def once(number):
        return Page[int](items=[42])

    assert [page.items async for page in offset_pages(once)] == [[42]]


async def test_cursor_pages_and_repeat_guard():
    calls = []

    async def fetch(cursor):
        calls.append(cursor)
        return Page[int](items=[1], next_cursor="next" if cursor is None else None)

    assert len([page async for page in cursor_pages(fetch)]) == 2
    assert calls == [None, "next"]

    async def repeat(cursor):
        return Page[int](items=[1], next_cursor="same")

    with pytest.raises(ValueError, match="cursor"):
        [page async for page in cursor_pages(repeat)]


async def test_offset_rejects_ignored_page_instead_of_repeating():
    async def fetch(number):
        return Page[int](items=[1], page=1, pages=3)

    with pytest.raises(ValueError, match="page"):
        [page async for page in offset_pages(fetch)]
