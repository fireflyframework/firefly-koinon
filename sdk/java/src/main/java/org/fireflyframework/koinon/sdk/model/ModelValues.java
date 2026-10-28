// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class ModelValues {
  private ModelValues() {}

  static JsonNode json(JsonNode value) {
    return value == null ? null : value.deepCopy();
  }

  static List<JsonNode> jsonList(List<JsonNode> value) {
    return value == null ? null : value.stream().map(ModelValues::json).toList();
  }

  @SuppressWarnings("unchecked")
  static <T> T freeze(T value) {
    if (value instanceof JsonNode node) return (T) node.deepCopy();
    if (value instanceof List<?> list) return (T) list.stream().map(ModelValues::freeze).toList();
    if (value instanceof Map<?, ?> map) {
      var copy = new LinkedHashMap<Object, Object>();
      map.forEach((key, item) -> copy.put(key, freeze(item)));
      return (T) Collections.unmodifiableMap(copy);
    }
    return value;
  }
}
