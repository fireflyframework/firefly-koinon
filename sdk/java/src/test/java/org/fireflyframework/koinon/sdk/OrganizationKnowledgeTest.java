// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.model.KnowledgeAnswerMode;
import org.fireflyframework.koinon.sdk.model.AnswerAudit;
import org.fireflyframework.koinon.sdk.model.OrganizationKnowledgeSettingsInput;
import org.fireflyframework.koinon.sdk.model.QueryResponse;
import org.fireflyframework.koinon.sdk.model.SearchResponse;
import org.junit.jupiter.api.Test;

final class OrganizationKnowledgeTest {
  @Test
  void typedPolicyRoundTripsActualHttpWithoutWorkspaceScopeOrAutomaticRetry() throws Exception {
    var codec = new JsonCodec();
    byte[] response;
    try (var input = getClass().getResourceAsStream("/canonical-model-fixtures.json")) {
      assertNotNull(input);
      response = codec.tree(input.readAllBytes()).get("fixtures")
          .get("OrganizationKnowledgeSettings").toString().getBytes(StandardCharsets.UTF_8);
    }
    var body = new AtomicReference<String>();
    var calls = new AtomicInteger();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      calls.incrementAndGet();
      assertEquals("/api/v1/tenants/north%2Fone/knowledge/settings", exchange.getRequestURI().getRawPath());
      assertNull(exchange.getRequestURI().getRawQuery());
      assertEquals("Bearer fixture", exchange.getRequestHeaders().getFirst("Authorization"));
      body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "fixture").build()) {
      var policy = client.organizationKnowledge("north/one").get();
      assertEquals("documents.rlm", policy.capabilities().documents().rlmModelRole().value());
      assertFalse(policy.capabilities().documents().rlmCuratedKnowledgeSupported());
      assertTrue(policy.capabilities().documents().rlmRecordedViewsRequired());
      assertEquals("RLM_DOCUMENT_VIEWS_REQUIRED", policy.capabilities().documents().rlmRecordedViewsReason().value());
      var change = OrganizationKnowledgeSettingsInput.empty().withExpectedRevision(policy.revision())
          .withDocuments(policy.documents().withAnswerMode(KnowledgeAnswerMode.RLM))
          .withStructured(policy.structured());
      var updated = client.organizationKnowledge("north/one").updateAsync(change).join();
      assertEquals(policy.revision(), updated.revision());
      var sent = codec.tree(body.get().getBytes(StandardCharsets.UTF_8));
      assertEquals(policy.revision().intValue(), sent.get("expected_revision").intValue());
      assertEquals("rlm", sent.get("documents").get("answer_mode").textValue());
      assertEquals(policy.structured().generationCandidates().intValue(),
          sent.get("structured").get("generation_candidates").intValue());
      assertEquals(2, calls.get());
    } finally { server.stop(0); }
  }

  @Test
  void directAppliedPolicyIsTypedWhileMissingHistoricalPolicyStaysNull() throws Exception {
    var codec = new JsonCodec();
    String snapshot;
    try (var input = getClass().getResourceAsStream("/canonical-model-fixtures.json")) {
      assertNotNull(input);
      snapshot = codec.tree(input.readAllBytes()).get("fixtures").get("OrganizationKnowledgeSnapshot").toString();
    }
    var search = codec.<SearchResponse>decode(("{\"hits\":[],\"knowledge_settings_snapshot\":"
        + snapshot + "}").getBytes(StandardCharsets.UTF_8), codec.type(SearchResponse.class));
    var query = codec.<QueryResponse>decode(("{\"query_id\":\"query\",\"execution_status\":\"OK\",\"knowledge_settings_snapshot\":"
        + snapshot + "}").getBytes(StandardCharsets.UTF_8), codec.type(QueryResponse.class));
    assertEquals(search.knowledgeSettingsSnapshot().digest(), query.knowledgeSettingsSnapshot().digest());
    var audit = codec.<AnswerAudit>decode(("{\"run_id\":\"run\",\"provenance_status\":\"recorded\",\"knowledge_settings_snapshot\":"
        + snapshot + "}").getBytes(StandardCharsets.UTF_8), codec.type(AnswerAudit.class));
    assertEquals(search.knowledgeSettingsSnapshot().digest(), audit.knowledgeSettingsSnapshot().digest());
    var old = codec.<SearchResponse>decode("{\"hits\":[]}".getBytes(StandardCharsets.UTF_8), codec.type(SearchResponse.class));
    assertNull(old.knowledgeSettingsSnapshot());
    var oldAudit = codec.<AnswerAudit>decode("{\"run_id\":\"old\",\"provenance_status\":\"not_recorded\"}".getBytes(StandardCharsets.UTF_8), codec.type(AnswerAudit.class));
    assertNull(oldAudit.knowledgeSettingsSnapshot());
  }
}
