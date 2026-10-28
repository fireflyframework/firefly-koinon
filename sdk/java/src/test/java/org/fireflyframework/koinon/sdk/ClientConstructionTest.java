// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import java.net.URI;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

final class ClientConstructionTest {
  @Test
  void rejectsUnsafeBaseAddressesWithoutCallingCredentialProvider() {
    var calls = new AtomicInteger();
    assertThrows(
        IllegalArgumentException.class,
        () ->
            KoinonClient.builder(URI.create("https://user:secret@example.test/api/v1"))
                .bearerToken(
                    () -> {
                      calls.incrementAndGet();
                      return "fictional-token";
                    })
                .build());
    assertEquals(0, calls.get());
  }
}
