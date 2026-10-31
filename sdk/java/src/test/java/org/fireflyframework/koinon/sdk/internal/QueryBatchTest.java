// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.api.QueryBatchesApi;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class QueryBatchTest {
  @Test void eightOperationsKeepScopeRevisionsKeysAndFreshCredentials() {
    var http = new BulkIntakeTest.InertHttp();
    var tokens = new AtomicInteger();
    try (var transport = new Transport(URI.create("https://inert.test/api/v1"), http, false,
        () -> "current-" + tokens.incrementAndGet(), new JsonCodec())) {
      var api = new QueryBatchesApi(transport, "north/office");
      api.capabilities(new QueryBatchScope("workspace"));
      api.create(QueryBatchCreate.empty(), "create-key");
      api.list(new QueryBatchFilter(2, 3));
      api.get("batch/one");
      api.items("batch/one", new QueryBatchFilter(2, 3));
      api.result("batch/one", "item/one");
      api.cancel("batch/one", new QueryBatchAction(7), "cancel-key");
      new QueryBatchesApi(transport, "south").reconcile("batch/one", "item/one",
          new QueryBatchAction(8), "inspect-key");
      assertEquals(8, http.requests.size());
      assertEquals(8, tokens.get());
      assertTrue(http.requests.get(5).uri().getRawPath().contains(
          "north%2Foffice/queries/batches/batch%2Fone/items/item%2Fone/result"));
      assertEquals("inspect-key", http.requests.get(7).headers().firstValue("Idempotency-Key").orElseThrow());
      assertEquals("{\"expected_revision\":8}", new String(http.bodies.get(7), StandardCharsets.UTF_8));
      assertTrue(http.requests.get(7).uri().getRawPath().contains("/tenants/south/"));
    }
  }

  @Test void unknownOutcomeDispatchesOnceWithoutModelReplay() {
    var http = new BulkIntakeTest.InertHttp();
    http.status = 503;
    http.response = "{\"code\":\"BULK_QUERY_OUTCOME_UNRESOLVED\"}";
    try (var transport = new Transport(URI.create("https://inert.test/api/v1"), http, false,
        () -> "token", new JsonCodec())) {
      var api = new QueryBatchesApi(transport, "north");
      assertThrows(ApiException.class, () -> api.reconcile("batch", "item", new QueryBatchAction(1), "stable"));
      assertEquals(1, http.requests.size());
    }
  }
}
