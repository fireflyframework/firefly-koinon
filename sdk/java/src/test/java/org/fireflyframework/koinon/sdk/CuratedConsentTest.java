// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.model.KnowledgeConfirmation;
import org.fireflyframework.koinon.sdk.model.PendingKnowledgeCommit;
import org.junit.jupiter.api.Test;

final class CuratedConsentTest {
  @Test void unresolvedCommitIsTypedAndNeverAutomaticallyRetried() throws Exception {
    var calls = new AtomicInteger();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1/tenants/north/knowledge-intents/intent/confirm", exchange -> {
      calls.incrementAndGet();
      assertEquals("explicit-consent", exchange.getRequestHeaders().getFirst("Idempotency-Key"));
      String request = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
      assertTrue(request.contains("\"confirm\":true"));
      byte[] bytes = "{\"status\":\"pending\",\"operation_id\":\"intent\",\"intent_id\":\"intent\",\"reason\":\"commit_outcome_unresolved\"}".getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(202, bytes.length);
      exchange.getResponseBody().write(bytes);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fresh").build()) {
      var outcome = client.knowledgeIntents("north").confirm("intent",
          new KnowledgeConfirmation(true, 1L, "a".repeat(64)), "explicit-consent");
      assertInstanceOf(PendingKnowledgeCommit.class, outcome);
      assertEquals(1, calls.get());
    } finally { server.stop(0); }
  }

  @Test void exactDocumentRevisionPairIsSeparateFromRawDigest() {
    String version = "12345678-1234-1234-1234-123456789abc";
    String extraction = "abcdef01-1234-1234-1234-123456789abc";
    var options = RequestOptions.defaults().ifMatch("raw-sha").documentRevision(version, extraction);
    assertEquals("raw-sha", options.headers().get("If-Match"));
    assertEquals(version, options.headers().get("X-Koinon-Source-Version"));
    assertEquals(extraction, options.headers().get("X-Koinon-Extraction"));
    assertThrows(IllegalArgumentException.class,
        () -> RequestOptions.defaults().documentRevision(version, null));
    assertThrows(IllegalArgumentException.class,
        () -> RequestOptions.defaults().documentRevision("malformed", extraction));
  }
}
