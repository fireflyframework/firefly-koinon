// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.sun.net.httpserver.HttpServer;
import java.lang.reflect.Method;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Stream;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.*;

final class CanonicalApiTest {
  private final JsonCodec codec = new JsonCodec();

  private JsonNode resource(String name) throws Exception {
    try (var in = getClass().getResourceAsStream("/" + name)) {
      return codec.tree(in.readAllBytes());
    }
  }

  @TestFactory
  Stream<DynamicTest> everyCanonicalOperationUsesItsRealHttpContract() throws Exception {
    var operations = resource("canonical-operation-fixtures.json");
    assertEquals(resource("canonical-methods.json").size(), operations.size());
    return java.util.stream.StreamSupport.stream(operations.spliterator(), false)
        .map(op -> DynamicTest.dynamicTest(op.path("operation").asText(), () -> verify(op, false)));
  }

  @TestFactory
  Stream<DynamicTest> asynchronousResourcesUseTheSameHttpContracts() throws Exception {
    var operations = resource("canonical-operation-fixtures.json");
    return java.util.stream.StreamSupport.stream(operations.spliterator(), false)
        .filter(op -> !op.path("operation").asText().equals("AssistantController.events"))
        .map(
            op ->
                DynamicTest.dynamicTest(
                    op.path("operation").asText() + "Async", () -> verify(op, true)));
  }

  private void verify(JsonNode op, boolean asynchronous) throws Exception {
    var observed = new AtomicReference<Throwable>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    var models = resource("canonical-model-fixtures.json").path("fixtures");
    server.createContext(
        "/",
        exchange -> {
          try {
            assertEquals(op.path("http").asText(), exchange.getRequestMethod());
            assertEquals(op.path("path").asText(), exchange.getRequestURI().getPath());
            assertEquals(
                "Bearer local-contract", exchange.getRequestHeaders().getFirst("Authorization"));
            assertEquals("trace-1", exchange.getRequestHeaders().getFirst("X-Test-Trace"));
            var actualQuery = new LinkedHashMap<String, String>();
            String query = exchange.getRequestURI().getRawQuery();
            if (query != null)
              for (String part : query.split("&")) {
                String[] pair = part.split("=", 2);
                actualQuery.put(
                    java.net.URLDecoder.decode(pair[0], StandardCharsets.UTF_8),
                    java.net.URLDecoder.decode(pair[1], StandardCharsets.UTF_8));
              }
            var expectedQuery = new LinkedHashMap<String, String>();
            op.path("query")
                .properties()
                .forEach(p -> expectedQuery.put(p.getKey(), p.getValue().asText()));
            assertEquals(expectedQuery, actualQuery);
            if (op.path("idempotency").asBoolean())
              assertEquals(
                  "stable-operation-key", exchange.getRequestHeaders().getFirst("Idempotency-Key"));
            if (op.path("precondition").asBoolean())
              assertEquals("\"revision-1\"", exchange.getRequestHeaders().getFirst("If-Match"));
            else assertNull(exchange.getRequestHeaders().getFirst("If-Match"));
            if (op.path("operation").asText().equals("AssistantController.events"))
              assertEquals("cursor-7", exchange.getRequestHeaders().getFirst("Last-Event-ID"));
            if (op.path("operation").asText().equals("ProfileController.avatar")
                || op.path("operation").asText().equals("ProfileController.person_avatar"))
              assertEquals("\"avatar-1\"", exchange.getRequestHeaders().getFirst("If-None-Match"));
            byte[] received = exchange.getRequestBody().readAllBytes();
            String request = op.path("request").isNull() ? null : op.path("request").asText();
            if (request != null) {
              if (op.path("encoding").asText().equals("multipart/form-data")) {
                assertTrue(
                    exchange
                        .getRequestHeaders()
                        .getFirst("Content-Type")
                        .startsWith("multipart/form-data; boundary="));
                String content = new String(received, StandardCharsets.UTF_8);
                assertTrue(content.contains("name=\"file\""));
                assertTrue(content.contains("source-content"));
                if (request.equals("SourceUpload"))
                  for (String field : List.of("workspace_id", "project_id", "parent_id", "mode"))
                    assertTrue(content.contains("name=\"" + field + "\""));
                if (request.equals("DocumentReplacement")) {
                  assertTrue(content.contains("acknowledge_chunk_invalidation"));
                  assertTrue(content.contains("true"));
                }
              } else if (request.equals("AvatarUpload")) {
                assertArrayEquals(new byte[] {1, 2, 3}, received);
                assertEquals("image/png", exchange.getRequestHeaders().getFirst("Content-Type"));
              } else assertEquals(models.path(request), codec.tree(received));
            } else assertEquals(0, received.length);
            byte[] response;
            if (op.path("operation").asText().equals("AssistantController.events")) {
              exchange.getResponseHeaders().set("Content-Type", "text/event-stream");
              response =
                  "id: event-8\nevent: message_delta\ndata: {\"text\":\"hello\"}\n\n"
                      .getBytes(StandardCharsets.UTF_8);
            } else if (op.path("response").asText().equals("BinaryDownload")) {
              exchange.getResponseHeaders().set("Content-Type", "image/jpeg");
              exchange.getResponseHeaders().set("ETag", "\"avatar-2\"");
              response = "original-bytes".getBytes(StandardCharsets.UTF_8);
            } else
              response =
                  op.path("response").asText().equals("void")
                      ? new byte[0]
                      : codec.encode(op.path("body"));
            exchange.sendResponseHeaders(
                op.path("status").asInt(), response.length == 0 ? -1 : response.length);
            if (response.length > 0) exchange.getResponseBody().write(response);
          } catch (Throwable error) {
            observed.set(error);
            exchange.sendResponseHeaders(500, -1);
          } finally {
            exchange.close();
          }
        });
    server.start();
    Path file = Files.createTempFile("koinon-java-api-", ".txt");
    Files.writeString(file, "source-content");
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"),
                http,
                false,
                () -> "local-contract",
                codec)) {
      Class<?> group =
          Class.forName("org.fireflyframework.koinon.sdk.api." + op.path("group").asText());
      boolean scoped = op.path("group_scoped").asBoolean();
      Object api =
          scoped
              ? group
                  .getConstructor(Transport.class, String.class)
                  .newInstance(transport, "tenant value")
              : group.getConstructor(Transport.class).newInstance(transport);
      Method method =
          Arrays.stream(group.getMethods())
              .filter(
                  m ->
                      m.getName().equals(op.path("method").asText() + (asynchronous ? "Async" : ""))
                          && m.getParameterCount() > 0
                          && m.getParameterTypes()[m.getParameterCount() - 1]
                              == RequestOptions.class)
              .findFirst()
              .orElseThrow();
      Object[] args = arguments(method, op, models, file);
      Object result;
      try {
        result = method.invoke(api, args);
      } catch (java.lang.reflect.InvocationTargetException error) {
        if (observed.get() != null) throw new AssertionError("HTTP contract", observed.get());
        throw error;
      }
      if (result instanceof CompletableFuture<?> task) result = task.get(3, TimeUnit.SECONDS);
      if (result instanceof EventStream<?> events) {
        var completed = new CompletableFuture<Object>();
        events.subscribe(
            new Flow.Subscriber<Object>() {
              public void onSubscribe(Flow.Subscription subscription) {
                subscription.request(Long.MAX_VALUE);
              }

              public void onNext(Object event) {
                completed.complete(event);
              }

              public void onError(Throwable error) {
                completed.completeExceptionally(error);
              }

              public void onComplete() {}
            });
        Object event = completed.get(3, TimeUnit.SECONDS);
        assertEquals("event-8", ((StreamEvent) event).id());
        events.close();
      } else if (result instanceof BinaryResponse binary) {
        assertEquals("original-bytes", new String(binary.content(), StandardCharsets.UTF_8));
        assertEquals("\"avatar-2\"", binary.etag());
      } else if (!op.path("response").asText().equals("void"))
        assertEquals(op.path("body"), codec.tree(codec.encode(result)));
      else assertNull(result);
      if (observed.get() != null) throw new AssertionError("HTTP contract", observed.get());
    } finally {
      server.stop(0);
      Files.deleteIfExists(file);
    }
  }

  private Object[] arguments(Method method, JsonNode op, JsonNode models, Path file)
      throws Exception {
    var params = method.getParameters();
    Object[] args = new Object[params.length];
    for (int i = 0; i < params.length; i++) {
      var parameter = params[i];
      Class<?> type = parameter.getType();
      String name = parameter.getName();
      if (type == RequestOptions.class) {
        var options = RequestOptions.defaults().header("X-Test-Trace", "trace-1");
        if (op.path("operation").asText().equals("AssistantController.events"))
          options = options.lastEventId("cursor-7");
        if (op.path("response").asText().equals("BinaryDownload"))
          options = options.header("If-None-Match", "\"avatar-1\"");
        args[i] = options;
      } else if (name.equals("idempotencyKey")) args[i] = "stable-operation-key";
      else if (name.equals("expectedRevision")) args[i] = "revision-1";
      else if (type == String.class) {
        String wire = name.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
        args[i] = op.path("ids").path(wire).asText();
      } else if (type == Long.class) {
        String wire = name.replaceAll("([a-z])([A-Z])", "$1_$2").toLowerCase(Locale.ROOT);
        args[i] = op.path("ids").path(wire).longValue();
      } else if (type == AttachmentUpload.class) args[i] = new AttachmentUpload(file, "text/plain");
      else if (type == DatasetFileUpload.class) args[i] = new DatasetFileUpload(file, "text/plain");
      else if (type == SourceUpload.class)
        args[i] =
            new SourceUpload(
                file, "text/plain", "workspace", "project", "collection", UploadMode.DOCUMENT);
      else if (type == DocumentReplacement.class)
        args[i] = new DocumentReplacement(file, "text/plain", true);
      else if (type == TableReplacement.class) args[i] = new TableReplacement(file, "text/plain");
      else if (type == AvatarUpload.class)
        args[i] = new AvatarUpload(new byte[] {1, 2, 3}, ImageMediaType.PNG);
      else if (name.equals("filter"))
        args[i] = codec.decode(codec.encode(op.path("query")), codec.type(type));
      else
        args[i] = codec.decode(codec.encode(models.path(type.getSimpleName())), codec.type(type));
    }
    return args;
  }

  @Test
  void mandatoryContentPreconditionsRejectBlankAndHeaderInjection() {
    try (var client =
        KoinonClient.builder(URI.create("http://127.0.0.1:9/api/v1"))
            .bearerToken(() -> "local")
            .build()) {
      for (String revision : List.of("", "bad\r\nvalue", "\"quoted\""))
        assertThrows(
            IllegalArgumentException.class,
            () ->
                client
                    .documents("tenant")
                    .reingest("document", DocumentReingestInput.empty(), revision));
    }
  }

  @Test
  void explicitProviderSecretClearIsSentWithoutLeakingIntoLogs() throws Exception {
    var request = new AtomicReference<JsonNode>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/api/v1/tenants/t/providers/p",
        exchange -> {
          request.set(codec.tree(exchange.getRequestBody().readAllBytes()));
          byte[] response = "{}".getBytes(StandardCharsets.UTF_8);
          exchange.sendResponseHeaders(200, response.length);
          exchange.getResponseBody().write(response);
          exchange.close();
        });
    server.start();
    try (var client =
        KoinonClient.builder(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"))
            .bearerToken(() -> "local")
            .build()) {
      client.providers("t").update("p", ProviderInput.empty().clearSecret().withEnabled(false));
      assertTrue(request.get().get("secret").isNull());
      assertFalse(request.get().get("enabled").asBoolean());
      assertEquals(2, request.get().size());
    } finally {
      server.stop(0);
    }
  }
}
