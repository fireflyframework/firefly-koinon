// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.model.OrganizationChatFilter;
import org.fireflyframework.koinon.sdk.model.OrganizationChatSettingsInput;
import org.junit.jupiter.api.Test;

final class OrganizationChatTest {
  @Test
  void defaultClearAndScopeAreExplicitAcrossActualHttp() throws Exception {
    var observed = new AtomicReference<String>();
    var query = new AtomicReference<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      observed.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      query.set(exchange.getRequestURI().getRawQuery());
      byte[] response = ("{\"tenant_id\":\"north\",\"default_agent_id\":null,\"revision\":2,"
          + "\"configured\":false,\"can_run\":false,\"status\":\"unconfigured\"}")
          .getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fixture").build()) {
      var current = client.organizationChat("north").get(OrganizationChatFilter.empty()
          .withWorkspaceId("workspace/one").withProjectId("project"));
      assertEquals("unconfigured", current.status().value());
      assertTrue(query.get().contains("workspace_id=workspace%2Fone"));
      client.organizationChat("north").updateAsync(OrganizationChatSettingsInput.empty()
          .clearDefaultAgentId().withExpectedRevision(current.revision())).join();
      assertTrue(observed.get().contains("\"default_agent_id\":null"));
      assertTrue(observed.get().contains("\"expected_revision\":2"));
    } finally {
      server.stop(0);
    }
  }
}
