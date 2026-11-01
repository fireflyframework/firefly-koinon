// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.CatalogLifecycleFilter;
import org.fireflyframework.koinon.sdk.model.CatalogUpdate;
import org.junit.jupiter.api.Test;

final class CatalogPreconditionTest {
  @Test
  void exactStateIsForwardedWhileLegacyConstructorsAndRequestOptionsRemainUsable() throws Exception {
    String stamp = "2026-11-01T15:01:02.123456Z";
    var codec = new JsonCodec();
    var calls = new AtomicInteger();
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      int call = calls.incrementAndGet();
      assertEquals("Bearer fixture", exchange.getRequestHeaders().getFirst("Authorization"));
      if (call == 1) assertNull(exchange.getRequestURI().getRawQuery());
      if (call == 2) {
        assertEquals("expected_updated_at=" + stamp,
            java.net.URLDecoder.decode(exchange.getRequestURI().getRawQuery(), StandardCharsets.UTF_8));
      }
      if (call == 3) {
        assertEquals(stamp, codec.tree(exchange.getRequestBody().readAllBytes()).get("expected_updated_at").textValue());
      }
      if (call == 4) {
        assertFalse(codec.tree(exchange.getRequestBody().readAllBytes()).has("expected_updated_at"));
      }
      byte[] body = "{\"id\":\"item\",\"tenant_id\":\"north\",\"kind\":\"collection\",\"name\":\"Name\",\"status\":\"ready\"}"
          .getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, body.length);
      exchange.getResponseBody().write(body);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"))
        .bearerToken(() -> "fixture").build()) {
      client.catalog("north").archive("item", RequestOptions.defaults());
      client.catalog("north").restoreAsync("item", CatalogLifecycleFilter.empty().withExpectedUpdatedAt(stamp)).join();
      client.catalog("north").update("item", CatalogUpdate.empty().withName("Updated")
          .withExpectedUpdatedAt(Instant.parse(stamp)));
      client.catalog("north").update("item", new CatalogUpdate(null, null, null));
      assertEquals(4, calls.get());
    } finally { server.stop(0); }
  }
}
