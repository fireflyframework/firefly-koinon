// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.io.IOException;

public final class JsonCodec {
  final ObjectMapper mapper =
      new ObjectMapper()
          .registerModule(new JavaTimeModule())
          .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
          .setDefaultPropertyInclusion(
              JsonInclude.Value.construct(JsonInclude.Include.NON_NULL, JsonInclude.Include.ALWAYS))
          .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
          .enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS)
          .enable(DeserializationFeature.USE_BIG_INTEGER_FOR_INTS)
          .enable(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
          .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

  public JavaType type(Class<?> type) {
    return mapper.constructType(type);
  }

  byte[] encode(Object value) {
    try {
      return mapper.writeValueAsBytes(value);
    } catch (IOException error) {
      throw new IllegalArgumentException("Request cannot be encoded as JSON", error);
    }
  }

  public <T> T decode(byte[] value, JavaType type) {
    try {
      return mapper.readValue(value, type);
    } catch (IOException error) {
      throw new IllegalStateException("API returned an invalid typed response", error);
    }
  }

  public <T> T event(String id, String kind, String data, Class<T> type) throws IOException {
    var envelope = mapper.createObjectNode().put("id", id).put("type", kind);
    JsonNode payload = mapper.readTree(data);
    if (payload == null) throw new IOException("Event stream data must be JSON");
    envelope.set("data", payload);
    return mapper.treeToValue(envelope, type);
  }

  public JsonNode tree(byte[] value) throws IOException {
    return mapper.readTree(value);
  }
}
