// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.fireflyframework.koinon.sdk.model.BrandingResetInput;
import org.fireflyframework.koinon.sdk.model.OrganizationBrandingInput;
import org.junit.jupiter.api.Test;

final class BrandingTest {
  @Test
  void publicDefaultsAndTenantRevisionRoutesUseTypedBodies() throws Exception {
    List<String> paths = new ArrayList<>();
    List<String> bodies = new ArrayList<>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      paths.add(exchange.getRequestMethod() + " " + exchange.getRequestURI().getRawPath());
      bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      String values = "{\"product_name\":\"Example\",\"assistant_name\":\"Assistant\","
          + "\"logo_light\":null,\"font_family\":\"Manrope\"}";
      String content = exchange.getRequestURI().getPath().equals("/api/v1/branding/defaults")
          ? values : "{\"tenant_id\":\"north/one\",\"revision\":2,\"origin\":\"organization\",\"branding\":" + values + "}";
      byte[] response = content.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fixture").build()) {
      var values = client.branding().defaults();
      assertEquals("Example", values.productName());
      assertEquals(2, client.branding("north/one").get().revision());
      client.branding("north/one").updateAsync(new OrganizationBrandingInput(1, values)).join();
      client.branding("north/one").reset(new BrandingResetInput(2));
      assertEquals(List.of("GET /api/v1/branding/defaults", "GET /api/v1/tenants/north%2Fone/branding",
          "PUT /api/v1/tenants/north%2Fone/branding", "POST /api/v1/tenants/north%2Fone/branding/reset"), paths);
      assertTrue(bodies.get(2).contains("\"expected_revision\":1"));
      assertTrue(bodies.get(2).contains("\"product_name\":\"Example\""));
      assertEquals("{\"expected_revision\":2}", bodies.get(3));
    } finally {
      server.stop(0);
    }
  }
}
