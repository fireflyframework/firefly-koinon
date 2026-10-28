# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lazy page traversal using endpoint-owned paging; no prefetch or write retries."""

from collections.abc import AsyncGenerator, Awaitable, Callable

from koinon_sdk.models import Page


async def offset_pages[T](
    fetch: Callable[[int], Awaitable[Page[T]]], first_page: int = 1
) -> AsyncGenerator[Page[T], None]:
    if type(first_page) is not int or first_page < 1:
        raise ValueError("The first page must be positive")
    requested = first_page
    while True:
        page = await fetch(requested)
        if page.page is not None and page.page != requested:
            raise ValueError("The server returned a different page; traversal stopped")
        yield page
        if page.page is None or not page.items:
            return
        pages = page.pages
        size = page.page_size or page.size
        if pages is None and page.total is not None and size is not None and size > 0:
            pages = (page.total + size - 1) // size
        if pages is None or requested >= pages:
            return
        requested += 1


async def cursor_pages[T](fetch: Callable[[str | None], Awaitable[Page[T]]]) -> AsyncGenerator[Page[T], None]:
    after = None
    seen: set[str] = set()
    while True:
        page = await fetch(after)
        cursor = page.next_cursor
        if cursor and cursor in seen:
            raise ValueError("The server repeated a cursor; traversal stopped")
        yield page
        if not cursor:
            return
        seen.add(cursor)
        after = cursor
