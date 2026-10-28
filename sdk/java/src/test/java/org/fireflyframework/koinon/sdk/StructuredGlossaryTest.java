// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.model.GlossaryTermCreate;
import org.fireflyframework.koinon.sdk.model.GlossaryTermUpdate;
import org.junit.jupiter.api.Test;

final class StructuredGlossaryTest {
  @Test
  void bothFamiliesPreserveOpaqueTimestampsAndExplicitNullAcrossSyncAndAsyncHttp() throws Exception {
    String revision = "2026-10-27T12:34:56.123456+00:00";
    var seen = new CopyOnWriteArrayList<String>();
    var fresh = new AtomicInteger();
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      assertEquals("north", exchange.getRequestHeaders().getFirst("X-Tenant-ID"));
      assertEquals("workspace", exchange.getRequestHeaders().getFirst("X-Workspace-ID"));
      String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
      seen.add(exchange.getRequestURI().getRawPath());
      if (!exchange.getRequestMethod().equals("POST")) {
        assertEquals("\"" + revision + "\"", exchange.getRequestHeaders().getFirst("If-Match"));
        assertTrue(exchange.getRequestURI().getRawPath().endsWith("term%2Fone"));
      }
      if (exchange.getRequestMethod().equals("PUT")) {
        assertTrue(body.contains("\"definition\":null"));
        assertTrue(body.contains("\"tags\":[]"));
        assertFalse(body.contains("synonyms"));
      }
      if (exchange.getRequestMethod().equals("DELETE")) exchange.sendResponseHeaders(204, -1);
      else {
        byte[] response = ("{\"id\":\"term\",\"updated_at\":\"" + revision + "\"}").getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, response.length);
        exchange.getResponseBody().write(response);
      }
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fresh-" + fresh.incrementAndGet()).build()) {
      var input = GlossaryTermCreate.empty().withTerm("Renewal").withDefinition("Original");
      var patch = GlossaryTermUpdate.empty().withDefinition(null).withTags(List.of());
      for (var api : List.of(client.structuredGlossary("north", "workspace"), client.structuredAgentGlossary("north", "workspace"))) {
        var read = api.create(input);
        assertEquals(revision, read.updatedAt());
        api.update("term/one", patch, read.updatedAt());
        api.remove("term/one", read.updatedAt());
        read = api.createAsync(input).join();
        assertEquals(revision, read.updatedAt());
        api.updateAsync("term/one", patch, read.updatedAt()).join();
        api.removeAsync("term/one", read.updatedAt()).join();
      }
      assertEquals(12, seen.size());
      assertEquals(12, fresh.get());
      assertEquals(6, seen.stream().filter(path -> path.contains("/agent/glossary")).count());
    } finally { server.stop(0); }
  }
}
