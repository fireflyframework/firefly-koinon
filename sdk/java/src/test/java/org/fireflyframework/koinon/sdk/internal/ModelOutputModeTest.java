// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import org.fireflyframework.koinon.sdk.model.ModelOutputMode;
import org.fireflyframework.koinon.sdk.model.ModelParameters;
import org.junit.jupiter.api.Test;

final class ModelOutputModeTest {
  @Test
  void preservesTypedChoiceExplicitNullAndOmission() throws Exception {
    var codec = new JsonCodec();
    var options = ModelParameters.empty();
    assertFalse(codec.tree(codec.encode(options)).has("output_mode"));
    for (var mode : ModelOutputMode.values()) {
      var body = codec.tree(codec.encode(options.withOutputMode(mode)));
      assertEquals(mode.value(), body.get("output_mode").textValue());
    }
    assertTrue(codec.tree(codec.encode(options.clearOutputMode())).get("output_mode").isNull());
    assertFalse(codec.tree(codec.encode(options.withOutputMode(ModelOutputMode.NATIVE)
        .omitOutputMode())).has("output_mode"));
  }
}
