// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

final class PlatformHealthTest {
  @Test
  void passiveTypedReadsRetainUnknownAndSendFreshCredentialWithoutBodies() throws Exception {
    var calls = new AtomicInteger();
    var credentials = new AtomicInteger();
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      int call = calls.incrementAndGet();
      assertEquals("GET", exchange.getRequestMethod());
      assertEquals("Bearer credential-" + call, exchange.getRequestHeaders().getFirst("Authorization"));
      assertEquals(0, exchange.getRequestBody().readAllBytes().length);
      String path = exchange.getRequestURI().getRawPath();
      assertTrue(path.startsWith("/api/v1/tenants/north%2Foffice/platform/"));
      String payload = call == 1
          ? "{\"tenant_id\":\"north/office\",\"checked_at\":\"2026-11-01T00:00:00Z\",\"summary\":{\"passed\":0,\"failed\":0,\"unknown\":0,\"disabled\":0},\"components\":[]}"
          : "{\"tenant_id\":\"north/office\",\"checked_at\":\"2026-11-01T00:00:00Z\",\"product\":\"koinon\",\"components\":[],\"serving_role\":\"unknown\",\"capabilities\":{\"knowledge_enabled\":false,\"mcp_enabled\":false,\"communications_enabled\":false,\"scheduled_consumers_enabled\":false},\"limits\":[],\"build_revision\":null,\"artifacts\":[]}";
      assertEquals(call == 1 ? "/api/v1/tenants/north%2Foffice/platform/health"
          : "/api/v1/tenants/north%2Foffice/platform/system-information", path);
      byte[] body = payload.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, body.length);
      exchange.getResponseBody().write(body);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1"))
        .bearerToken(() -> "credential-" + credentials.incrementAndGet()).build()) {
      var health = client.platformHealth("north/office").health();
      var info = client.platformHealth("north/office").systemInformationAsync().join();
      assertEquals(0, health.summary().unknown().intValue());
      assertNull(info.buildRevision());
      assertEquals("unknown", info.servingRole().value());
      assertEquals(2, calls.get());
    } finally { server.stop(0); }
  }
}
