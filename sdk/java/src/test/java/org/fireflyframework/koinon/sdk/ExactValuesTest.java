// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.node.BooleanNode;
import com.fasterxml.jackson.databind.node.TextNode;
import java.math.BigDecimal;
import java.math.BigInteger;
import org.junit.jupiter.api.Test;

final class ExactValuesTest {
  @Test
  void preservesPrecisionScaleAndSafeIntegerBoundary() {
    var value = new BigDecimal("12345678901234567890.00100");
    assertEquals("12345678901234567890.00100", ExactValues.decimal(value).textValue());
    assertEquals(value, ExactValues.decimalValue(ExactValues.decimal(value)));
    assertTrue(ExactValues.integer(new BigInteger("9007199254740991")).isIntegralNumber());
    assertEquals(
        "9007199254740992", ExactValues.integer(new BigInteger("9007199254740992")).textValue());
    assertEquals(
        "-9007199254740992", ExactValues.integer(new BigInteger("-9007199254740992")).textValue());
    assertEquals(
        new BigInteger("9007199254740992"),
        ExactValues.integerValue(new TextNode("9007199254740992")));
  }

  @Test
  void doesNotCoerceNonNumericCells() {
    assertThrows(IllegalArgumentException.class, () -> ExactValues.decimalValue(BooleanNode.TRUE));
    assertThrows(
        IllegalArgumentException.class, () -> ExactValues.integerValue(new TextNode("1.25")));
    assertThrows(IllegalArgumentException.class, () -> ExactValues.decimalValue(new TextNode("")));
    assertThrows(
        IllegalArgumentException.class, () -> ExactValues.decimalValue(new TextNode("NaN")));
  }
}
