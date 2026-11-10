// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ConcurrentLinkedQueue;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class KnowledgeModesTest {
  @Test
  void typedModeOperationsKeepExactTenantIdsKeysAndCursorParameters() throws Exception {
    var codec = new JsonCodec();
    com.fasterxml.jackson.databind.JsonNode fixtures;
    try (var stream = getClass().getResourceAsStream("/canonical-model-fixtures.json")) {
      assertNotNull(stream);
      fixtures = codec.tree(stream.readAllBytes()).get("fixtures");
    }
    var calls = new ConcurrentLinkedQueue<String>();
    var keys = new ConcurrentLinkedQueue<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      calls.add(exchange.getRequestMethod() + " " + exchange.getRequestURI());
      var key = exchange.getRequestHeaders().getFirst("Idempotency-Key");
      if (key != null) keys.add(key);
      exchange.getRequestBody().readAllBytes();
      String path = exchange.getRequestURI().getPath();
      String name = path.endsWith("/current") ? "KnowledgeModeCurrentView"
          : path.endsWith("/targets") ? "KnowledgeModeTargetPage" : "KnowledgeModeTransitionView";
      byte[] response = fixtures.get(name).toString().getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fixture").build()) {
      var input = codec.<OrganizationKnowledgeSettingsInput>decode(
          fixtures.get("OrganizationKnowledgeSettingsInput").toString().getBytes(StandardCharsets.UTF_8),
          codec.type(OrganizationKnowledgeSettingsInput.class));
      var api = client.knowledgeModes("north/one");
      assertNotNull(api.create(input, "stable"));
      assertNotNull(api.current());
      assertNotNull(api.get("transition/one"));
      assertNotNull(api.targets("transition/one", KnowledgeModeTargetFilter.empty().withAfter("cursor/one").withLimit(25)));
      var revision = KnowledgeModeRevisionInput.empty().withExpectedRevision(2L);
      assertNotNull(api.cancel("transition/one", revision));
      assertNotNull(api.retryAsync("transition/one", revision).join());
    } finally { server.stop(0); }
    assertEquals(6, calls.size());
    assertTrue(calls.stream().allMatch(value -> value.contains("/tenants/north%2Fone/knowledge/settings/transitions")));
    assertTrue(calls.stream().anyMatch(value -> value.contains("transition%2Fone/targets?")
        && value.contains("after=cursor%2Fone") && value.contains("limit=25")));
    assertEquals(java.util.List.of("stable"), java.util.List.copyOf(keys));
  }
}
