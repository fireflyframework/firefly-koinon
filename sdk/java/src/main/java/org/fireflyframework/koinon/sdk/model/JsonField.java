// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.fasterxml.jackson.databind.deser.ContextualDeserializer;
import java.io.IOException;

/** A present field, including explicit null; a null wrapper means omission. */
@JsonDeserialize(using = JsonField.Decoder.class)
public record JsonField<T>(T value) {
  public JsonField {
    value = ModelValues.freeze(value);
  }

  public static <T> JsonField<T> of(T value) {
    return new JsonField<>(value);
  }

  public static <T> JsonField<T> clear() {
    return new JsonField<>(null);
  }

  @Override
  @JsonValue
  public T value() {
    return ModelValues.freeze(value);
  }

  @Override
  public String toString() {
    return "JsonField[<redacted>]";
  }

  public static final class Decoder extends JsonDeserializer<JsonField<?>>
      implements ContextualDeserializer {
    private final JavaType valueType;

    public Decoder() {
      this.valueType = null;
    }

    private Decoder(JavaType valueType) {
      this.valueType = valueType;
    }

    @Override
    public JsonDeserializer<?> createContextual(
        DeserializationContext context, BeanProperty property) {
      JavaType type = property == null ? context.getContextualType() : property.getType();
      return new Decoder(
          type != null && type.containedTypeCount() > 0
              ? type.containedType(0)
              : context.constructType(Object.class));
    }

    @Override
    public JsonField<?> deserialize(JsonParser parser, DeserializationContext context)
        throws IOException {
      return new JsonField<>(context.readValue(parser, valueType));
    }

    @Override
    public JsonField<?> getNullValue(DeserializationContext context) {
      return JsonField.clear();
    }

    @Override
    public JsonField<?> getAbsentValue(DeserializationContext context) {
      return null;
    }
  }
}
