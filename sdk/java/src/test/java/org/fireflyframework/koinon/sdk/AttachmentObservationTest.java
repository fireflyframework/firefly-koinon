// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.fireflyframework.koinon.sdk.model.AttachmentObservation;
import org.junit.jupiter.api.Test;

final class AttachmentObservationTest {
  @Test
  void oldConstructorAndMissingConfiguredFieldRemainCompatible() throws Exception {
    var legacy = new AttachmentObservation(true, "Checked");
    assertFalse(legacy.configured());
    var decoded = new ObjectMapper().readValue(
        "{\"available\":null,\"reason\":\"Provider unverified\"}", AttachmentObservation.class);
    assertFalse(decoded.configured());
    assertNull(decoded.available());
  }

  @Test
  void configuredAdapterDoesNotImplyObservedHealth() {
    var observation = new AttachmentObservation(null, "Provider unverified", true);
    assertTrue(observation.configured());
    assertNull(observation.available());
  }
}
