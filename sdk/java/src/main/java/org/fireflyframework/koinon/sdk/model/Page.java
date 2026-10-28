// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.util.List;
import java.util.Map;

/** Optional page metadata remains absent for items-only and cursor endpoints. */
public record Page<T>(
    List<T> items,
    Long total,
    Integer page,
    Integer size,
    Integer pageSize,
    Integer pages,
    String nextCursor,
    Map<String, AuthorSummary> actors,
    Map<String, CatalogSummary> summaries) {
  public Page {
    items = List.copyOf(java.util.Objects.requireNonNull(items, "Page items are required"));
    actors = actors == null ? Map.of() : Map.copyOf(actors);
    summaries = summaries == null ? Map.of() : Map.copyOf(summaries);
  }

  public Page(List<T> items, Long total, Integer page, Integer size, Integer pageSize, Integer pages,
              String nextCursor, Map<String, AuthorSummary> actors) {
    this(items, total, page, size, pageSize, pages, nextCursor, actors, Map.of());
  }

  public Page(List<T> items) {
    this(items, null, null, null, null, null, null, Map.of(), Map.of());
  }
}
