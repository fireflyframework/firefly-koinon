// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import java.util.Arrays;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import com.sun.net.httpserver.HttpServer;
import org.fireflyframework.koinon.sdk.api.McpApi;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.Test;

final class McpOAuthClientsTest {
  @Test
  void organizationRegistrationGroupIsAvailableWithoutChangingGlobalConnection() throws Exception {
    assertTrue(Arrays.stream(KoinonClient.class.getMethods()).anyMatch(method -> method.getName().equals("mcpOAuthClients")));
    assertTrue(Arrays.stream(McpApi.class.getMethods()).anyMatch(method -> method.getName().equals("organizationConnection")));
    assertTrue(Arrays.stream(McpApi.class.getMethods()).anyMatch(method -> method.getName().equals("connection") && method.getParameterCount() == 0));
    assertNotNull(McpApi.class.getConstructor(Transport.class));
    assertEquals(McpRegisteredClientClientAuth.class, McpRegisteredClient.class.getMethod("clientAuth").getReturnType());
  }

  @Test
  void scopedSyncAndAsyncOperationsPreserveGlobalCompatibilityAndTypedRevisionBodies() throws Exception {
    List<String> paths = new ArrayList<>(), bodies = new ArrayList<>(), queries = new ArrayList<>();
    String value = """
        {"id":"row/one","tenant_id":"north/team","client_id":"koinon_org_owned",
        "name":"Research","client_type":"confidential","redirect_uris":["https://client.example/callback"],
        "scopes":["catalog:read"],"enabled":true,"revision":2,"created_at":"2026-10-29T00:00:00Z",
        "updated_at":"2026-10-29T01:00:00Z","created_by":"issuer|admin","updated_by":"issuer|admin"}
        """;
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      paths.add(exchange.getRequestMethod() + " " + exchange.getRequestURI().getRawPath());
      bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      queries.add(exchange.getRequestURI().getRawQuery());
      String path = exchange.getRequestURI().getPath();
      String response = path.endsWith("/connection")
          ? "{\"enabled\":true,\"endpoint\":\"https://organization.example/mcp\",\"authentication\":[\"oauth\"],\"oauth_enabled\":true,\"oauth_registration\":\"pre_registered\",\"supported_scopes\":[\"catalog:read\"],\"tools\":[],\"review\":{\"supported\":true}}"
          : path.endsWith("/readiness")
          ? "{\"ready\":true,\"endpoint_enabled\":true,\"oauth_enabled\":true,\"encryption_configured\":true,\"missing_configuration\":[]}"
          : exchange.getRequestMethod().equals("POST")
          ? "{\"client\":" + value + ",\"client_secret\":\"owned-once\"}"
          : path.endsWith("/oauth-clients")
          ? "{\"items\":[" + value + "],\"total\":11,\"page\":2,\"page_size\":10,\"pages\":2}"
          : value;
      byte[] bytes = response.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, bytes.length);
      exchange.getResponseBody().write(bytes);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"))
        .bearerToken(() -> "owned-identity").build()) {
      var api = client.mcpOAuthClients("north/team");
      var filter = McpOAuthClientFilter.empty().withQ("Research").withStatus(McpOAuthClientStatus.ENABLED)
          .withPage(2).withPageSize(10).withSort(McpOAuthClientSort.UPDATED_AT).withOrder(McpOAuthClientOrder.DESC);
      var input = McpOAuthClientInput.empty().withName("Research").withClientType(McpRegisteredClientClientAuth.CONFIDENTIAL)
          .withRedirectUris(List.of("https://client.example/callback")).withScopes(List.of(McpOAuthScope.CATALOG_READ));
      var patch = McpOAuthClientPatch.empty().withExpectedRevision(1).withEnabled(false);
      assertTrue(client.mcp().connection().enabled());
      assertTrue(client.mcp().organizationConnection("north/team").enabled());
      assertTrue(api.readiness().ready());
      assertEquals(11, api.list(filter).total());
      var issued = api.create(input);
      assertEquals("owned-once", issued.clientSecret());
      assertFalse(issued.toString().contains("owned-once"));
      assertEquals("koinon_org_owned", api.get("row/one").clientId());
      api.update("row/one", patch);
      api.rotateSecret("row/one", new McpOAuthClientRevision(2));
      client.mcp().organizationConnectionAsync("north/team").join();
      api.readinessAsync().join();
      api.listAsync(filter).join();
      api.createAsync(input).join();
      api.getAsync("row/one").join();
      api.updateAsync("row/one", patch).join();
      api.rotateSecretAsync("row/one", new McpOAuthClientRevision(2)).join();
      String prefix = "/api/v1/tenants/north%2Fteam/mcp";
      assertEquals(List.of("GET /api/v1/mcp/connection", "GET " + prefix + "/connection",
          "GET " + prefix + "/oauth-clients/readiness", "GET " + prefix + "/oauth-clients",
          "POST " + prefix + "/oauth-clients", "GET " + prefix + "/oauth-clients/row%2Fone",
          "PATCH " + prefix + "/oauth-clients/row%2Fone", "POST " + prefix + "/oauth-clients/row%2Fone/rotate-secret"), paths.subList(0, 8));
      assertEquals(paths.subList(1, 8), paths.subList(8, 15));
      assertTrue(queries.get(3).contains("status=enabled") && queries.get(3).contains("sort=updated_at") && queries.get(3).contains("order=desc"));
      assertTrue(bodies.get(6).contains("\"enabled\":false") && !bodies.get(6).contains("\"name\""));
      assertEquals("{\"expected_revision\":2}", bodies.get(7));
    } finally {
      server.stop(0);
    }
  }
}
