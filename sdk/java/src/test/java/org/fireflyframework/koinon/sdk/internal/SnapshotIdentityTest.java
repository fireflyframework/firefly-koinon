// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Arrays;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class SnapshotIdentityTest {
  @Test
  void optionalIdentityKeepsPreviousResponseConstructors() {
    for (var model : java.util.List.of(ConversationSnapshot.class, ExportReview.class,
        ShareReview.class, SharedConversation.class)) {
      int previousArity = model.getRecordComponents().length - 1;
      assertTrue(Arrays.stream(model.getConstructors())
          .anyMatch(value -> value.getParameterCount() == previousArity), model.getName());
    }
  }

  @Test
  void savedIdentityAndHistoricalNullDeserializeSeparately() throws Exception {
    var codec = new JsonCodec();
    var saved = codec.mapper.readValue("{\"identity\":{\"product_name\":\"North\","
        + "\"assistant_name\":\"North helper\",\"branding_revision\":7,"
        + "\"branding_origin\":\"organization\",\"branding_sha256\":\"" + "a".repeat(64)
        + "\"}}", SharedConversation.class);
    assertEquals("North helper", saved.identity().assistantName());
    assertEquals(7, saved.identity().brandingRevision());
    assertNull(codec.mapper.readValue("{}", SharedConversation.class).identity());
  }
}
