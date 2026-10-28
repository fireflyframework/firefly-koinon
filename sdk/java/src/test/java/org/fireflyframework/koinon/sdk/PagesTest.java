// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.model.Page;
import org.junit.jupiter.api.Test;

final class PagesTest {
  @Test
  void lazilyReadsOnlyDeclaredServerPages() {
    var calls = new AtomicInteger();
    var rows =
        Pages.numbered(
            page -> {
              calls.incrementAndGet();
              return new Page<>(List.of(page), 2L, page, null, 1, 2, null, Map.of());
            },
            1);
    assertEquals(0, calls.get());
    var read = new ArrayList<Integer>();
    rows.forEach(read::add);
    assertEquals(List.of(1, 2), read);
    assertEquals(2, calls.get());
    var once = new AtomicInteger();
    Pages.numbered(
            page -> {
              once.incrementAndGet();
              return new Page<>(List.of("only"));
            },
            1)
        .forEach(value -> {});
    assertEquals(1, once.get());
  }

  @Test
  void detectsIgnoredPageNumbersAndRepeatedOpaqueCursors() {
    var mismatch =
        Pages.numbered(page -> new Page<>(List.of(1), 4L, 1, null, 1, 4, null, Map.of()), 2)
            .iterator();
    assertThrows(IllegalStateException.class, mismatch::hasNext);
    var repeated =
        Pages.cursor(
                cursor -> new Page<>(List.of(1), null, null, null, null, null, "same", Map.of()))
            .iterator();
    assertEquals(1, repeated.next());
    assertThrows(IllegalStateException.class, repeated::hasNext);
  }

  @Test
  void cursorFetchesServerCursorAndStopsAtEnd() {
    var calls = new ArrayList<String>();
    Iterable<String> rows =
        Pages.cursor(
            cursor -> {
              calls.add(cursor);
              return new Page<>(
                  List.of(cursor == null ? "first" : "second"),
                  null,
                  null,
                  null,
                  null,
                  null,
                  cursor == null ? "opaque+/=" : null,
                  Map.of());
            });
    var result = new ArrayList<String>();
    rows.forEach(result::add);
    assertEquals(List.of("first", "second"), result);
    assertEquals(2, calls.size());
    assertNull(calls.get(0));
    assertEquals("opaque+/=", calls.get(1));
  }
}
