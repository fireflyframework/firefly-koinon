// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.BigIntegerNode;
import com.fasterxml.jackson.databind.node.TextNode;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.Objects;

/**
 * Explicit conversions for numeric business cells; identifiers are never converted automatically.
 */
public final class ExactValues {
  private static final BigInteger SAFE_INTEGER_LIMIT = BigInteger.valueOf(9_007_199_254_740_991L);

  private ExactValues() {}

  public static TextNode decimal(BigDecimal value) {
    return new TextNode(Objects.requireNonNull(value).toPlainString());
  }

  public static JsonNode integer(BigInteger value) {
    Objects.requireNonNull(value);
    return value.abs().compareTo(SAFE_INTEGER_LIMIT) > 0
        ? new TextNode(value.toString())
        : new BigIntegerNode(value);
  }

  public static BigDecimal decimalValue(JsonNode value) {
    String text = numericText(value);
    if (!text.matches("-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"))
      throw new IllegalArgumentException("Expected an exact decimal cell");
    return new BigDecimal(text);
  }

  public static BigInteger integerValue(JsonNode value) {
    String text = numericText(value);
    if (!text.matches("-?(?:0|[1-9][0-9]*)"))
      throw new IllegalArgumentException("Expected an exact integer cell");
    return new BigInteger(text);
  }

  private static String numericText(JsonNode value) {
    if (value == null || !(value.isNumber() || value.isTextual()))
      throw new IllegalArgumentException("Expected a numeric cell");
    return value.asText();
  }
}
