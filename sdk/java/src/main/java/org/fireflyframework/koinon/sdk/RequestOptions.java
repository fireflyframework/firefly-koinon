// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/** Immutable options shared by synchronous, asynchronous, binary and streaming requests. */
public record RequestOptions(
    Map<String, String> query, Map<String, String> headers, Duration timeout) {
  public RequestOptions {
    query = Map.copyOf(query);
    headers = Map.copyOf(headers);
    Objects.requireNonNull(timeout);
    if (timeout.isNegative() || timeout.isZero())
      throw new IllegalArgumentException("Timeout must be positive");
  }

  public static RequestOptions defaults() {
    return new RequestOptions(Map.of(), Map.of(), Duration.ofSeconds(30));
  }

  public RequestOptions query(String name, String value) {
    var next = new LinkedHashMap<>(query);
    if (value == null) next.remove(name);
    else next.put(name, value);
    return new RequestOptions(next, headers, timeout);
  }

  public RequestOptions query(String name, long value) {
    return query(name, Long.toString(value));
  }

  public RequestOptions query(String name, boolean value) {
    return query(name, Boolean.toString(value));
  }

  public RequestOptions header(String name, String value) {
    var next = new LinkedHashMap<>(headers);
    next.put(name, value);
    return new RequestOptions(query, next, timeout);
  }

  public RequestOptions timeout(Duration value) {
    return new RequestOptions(query, headers, value);
  }

  public RequestOptions idempotencyKey(String value) {
    return header("Idempotency-Key", value);
  }

  public RequestOptions lastEventId(String value) {
    if (value == null || value.chars().anyMatch(c -> c == 0 || c == 10 || c == 13))
      throw new IllegalArgumentException("Last-Event-ID cannot contain line breaks or NUL");
    return header("Last-Event-ID", value);
  }

  public RequestOptions ifMatch(String value) {
    return header("If-Match", value);
  }

  /** Bind the exact ingestion revision pair, separately from the original byte digest. */
  public RequestOptions documentRevision(String sourceVersionId, String extractionId) {
    if ((sourceVersionId == null) != (extractionId == null))
      throw new IllegalArgumentException("Supply the exact source version and extraction together");
    if (sourceVersionId == null) return this;
    return header("X-Koinon-Source-Version", java.util.UUID.fromString(sourceVersionId).toString())
        .header("X-Koinon-Extraction", java.util.UUID.fromString(extractionId).toString());
  }
}
