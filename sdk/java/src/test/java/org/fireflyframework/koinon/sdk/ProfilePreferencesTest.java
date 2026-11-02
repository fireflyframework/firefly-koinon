// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.model.ProfileUpdate;
import org.fireflyframework.koinon.sdk.model.UserProfile;
import org.junit.jupiter.api.Test;

final class ProfilePreferencesTest {
  @Test
  void initializedPreferencesKeepTypedLocaleAndLegacyConstructors() throws Exception {
    var observed = new AtomicReference<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1/profile", exchange -> {
      observed.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      byte[] response = ("{\"subject\":\"issuer|self\",\"display_name\":\"Self\","
          + "\"locale\":\"es-ES-u-ca-gregory-hc-h23\",\"time_zone\":\"Europe/Madrid\","
          + "\"response_language\":\"auto\",\"preferences_initialized\":true}")
          .getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fixture").build()) {
      var previous = new ProfileUpdate(null, null, null, null);
      var result = client.profile().updateAsync(previous.withInitializeOnly(true)
          .withLocale("es-ES-u-ca-gregory-hc-h23").withTimeZone("Europe/Madrid")).join();
      assertTrue(result.preferencesInitialized());
      assertEquals("es-ES-u-ca-gregory-hc-h23", result.locale());
      assertTrue(observed.get().contains("\"initialize_only\":true"));
      assertFalse(observed.get().contains("response_language"));
      var oldResponse = new UserProfile("issuer|self", "Self", "en-US", "UTC", "auto", null, null);
      assertNull(oldResponse.preferencesInitialized());
    } finally {
      server.stop(0);
    }
  }
}
