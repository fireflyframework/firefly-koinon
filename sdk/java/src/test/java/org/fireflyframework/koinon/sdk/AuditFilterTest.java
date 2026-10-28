// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.model.AuditFilter;
import org.junit.jupiter.api.Test;

final class AuditFilterTest {
  @Test
  void explicitCalendarZoneSurvivesActualHttpAndCapabilitiesRemainScoped() throws Exception {
    var observed = new AtomicReference<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/api/v1",
        exchange -> {
          observed.set(exchange.getRequestURI().getRawQuery());
          String body =
              exchange.getRequestURI().getPath().endsWith("/context")
                  ? "{\"subject\":\"issuer|user\",\"workspace_permissions\":{\"workspace\":[\"catalog:read\"]}}"
                  : "{\"items\":[],\"total\":0,\"page\":2,\"page_size\":3}";
          byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
          exchange.getResponseHeaders().set("Content-Type", "application/json");
          exchange.sendResponseHeaders(200, bytes.length);
          exchange.getResponseBody().write(bytes);
          exchange.close();
        });
    server.start();
    try (var client =
        KoinonClient.builder(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"))
            .bearerToken(() -> "fresh")
            .build()) {
      var filter =
          AuditFilter.empty()
              .withQ("Málaga")
              .withAction("catalog.updated")
              .withSubject("issuer|user")
              .withFromDate("2026-03-08")
              .withThroughDate("2026-03-08")
              .withTimeZone("America/Los_Angeles")
              .withPage(2)
              .withPageSize(3)
              .withSort("action")
              .withOrder("asc");
      assertEquals(0L, client.audit("tenant").list(filter).total());
      assertTrue(observed.get().contains("from_date=2026-03-08"));
      assertTrue(observed.get().contains("time_zone=America%2FLos_Angeles"));
      assertEquals(
          Map.of("workspace", java.util.List.of("catalog:read")),
          client.platform().context().workspacePermissions());
    } finally {
      server.stop(0);
    }
  }
}
