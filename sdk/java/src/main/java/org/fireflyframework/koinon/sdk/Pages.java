// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.function.Function;
import java.util.function.IntFunction;
import org.fireflyframework.koinon.sdk.model.Page;

/** Lazy iteration of server pages; these helpers never slice a client-side collection. */
public final class Pages {
  private Pages() {}

  /** Items-only endpoints are fetched once. The callback owns the endpoint-specific filters. */
  public static <T> Iterable<T> numbered(IntFunction<Page<T>> fetch, int firstPage) {
    Objects.requireNonNull(fetch);
    if (firstPage < 1) throw new IllegalArgumentException("Page numbers start at one");
    return () ->
        new Iterator<>() {
          private Iterator<T> items = List.<T>of().iterator();
          private int nextPage = firstPage;
          private long seen;
          private boolean finished;

          public boolean hasNext() {
            while (!items.hasNext() && !finished) {
              int requested = nextPage;
              var page = Objects.requireNonNull(fetch.apply(requested));
              if (page.page() != null && page.page() != requested)
                throw new IllegalStateException("Server returned a different page number");
              seen += page.items().size();
              Integer size = page.pageSize() == null ? page.size() : page.pageSize();
              finished =
                  page.items().isEmpty()
                      || (page.total() != null
                          && (size == null ? seen : (long) requested * size) >= page.total())
                      || (page.pages() != null && requested >= page.pages())
                      || (size != null && page.items().size() < size)
                      || (page.page() == null && size == null);
              if (!finished) {
                if (requested == Integer.MAX_VALUE)
                  throw new IllegalStateException("Page number limit reached");
                nextPage++;
              }
              items = page.items().iterator();
            }
            return items.hasNext();
          }

          public T next() {
            if (!hasNext()) throw new NoSuchElementException();
            return items.next();
          }
        };
  }

  /** The first callback receives null; subsequent calls receive the server's opaque cursor. */
  public static <T> Iterable<T> cursor(Function<String, Page<T>> fetch) {
    Objects.requireNonNull(fetch);
    return () ->
        new Iterator<>() {
          private Iterator<T> items = List.<T>of().iterator();
          private final HashSet<String> cursors = new HashSet<>();
          private String nextCursor;
          private boolean finished;

          public boolean hasNext() {
            while (!items.hasNext() && !finished) {
              var page = Objects.requireNonNull(fetch.apply(nextCursor));
              nextCursor = page.nextCursor();
              finished = nextCursor == null || nextCursor.isEmpty();
              if (!finished && !cursors.add(nextCursor))
                throw new IllegalStateException("Server repeated a page cursor");
              items = page.items().iterator();
            }
            return items.hasNext();
          }

          public T next() {
            if (!hasNext()) throw new NoSuchElementException();
            return items.next();
          }
        };
  }
}
