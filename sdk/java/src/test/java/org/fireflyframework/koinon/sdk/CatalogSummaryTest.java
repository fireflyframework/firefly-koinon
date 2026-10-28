// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.model.CatalogFilter;
import org.junit.jupiter.api.Test;

final class CatalogSummaryTest {
  @Test
  void existingCatalogFilterConstructorRemainsAvailable() {
    var filter = new CatalogFilter("document", null, null, null, false, "library", "policy", "ready", 1, 25, "name", "asc");
    assertEquals("document", filter.kind());
    assertNull(filter.format());
    assertNull(filter.tag());
  }

  @Test
  void filtersAndNullableSummaryCountsSurviveHttp() throws Exception {
    var observed = new AtomicReference<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      observed.set(exchange.getRequestURI().getRawQuery());
      byte[] bytes = "{\"items\":[],\"summaries\":{\"file\":{\"format\":\"pdf\",\"size_bytes\":12,\"row_count\":null,\"tags\":[\"pdf\",\"reviewed\"]}}}".getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, bytes.length);
      exchange.getResponseBody().write(bytes);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fresh").build()) {
      var page = client.catalog("north").list(CatalogFilter.empty().withFormat("pdf").withTag("reviewed").withSort("kind"));
      assertTrue(observed.get().contains("format=pdf"));
      assertTrue(observed.get().contains("tag=reviewed"));
      assertEquals("pdf", page.summaries().get("file").format());
      assertEquals(12L, page.summaries().get("file").sizeBytes());
      assertNull(page.summaries().get("file").rowCount());
    } finally {
      server.stop(0);
    }
  }
}
