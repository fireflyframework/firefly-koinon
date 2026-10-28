// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.junit.jupiter.api.Test;

final class TransportTest {
  private record Value(String name, boolean active) {}

  @Test
  void typedRequestsPreserveFalseAndRefreshCredentials() throws Exception {
    var calls = new AtomicInteger();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/api/v1/profile",
        exchange -> {
          assertEquals(
              "Bearer token-" + calls.get(),
              exchange.getRequestHeaders().getFirst("Authorization"));
          assertEquals(
              java.util.Set.of("page=2", "q=a+b"),
              java.util.Set.of(exchange.getRequestURI().getRawQuery().split("&")));
          String request =
              new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
          assertTrue(request.contains("\"active\":false"));
          byte[] body = "{\"name\":\"Málaga\",\"active\":false}".getBytes(StandardCharsets.UTF_8);
          exchange.sendResponseHeaders(200, body.length);
          exchange.getResponseBody().write(body);
          exchange.close();
        });
    server.start();
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1"),
                http,
                false,
                () -> "token-" + calls.incrementAndGet(),
                new JsonCodec())) {
      var options = RequestOptions.defaults().query("page", 2).query("q", "a b");
      Value first =
          transport.json(
              "PATCH", "/profile", new Value("name", false), options, transport.type(Value.class));
      assertEquals("Málaga", first.name());
      assertFalse(first.active());
      transport
          .jsonAsync(
              "PATCH", "/profile", new Value("name", false), options, transport.type(Value.class))
          .get(2, TimeUnit.SECONDS);
      assertEquals(2, calls.get());
    } finally {
      server.stop(0);
    }
  }

  @Test
  void mapsNativeProblemAndConditionalBinaryMetadata() throws Exception {
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/problem",
        exchange -> {
          byte[] body =
              "{\"code\":\"ACCESS_DENIED\",\"detail\":\"No access\",\"transactionId\":\"native-ref\"}"
                  .getBytes(StandardCharsets.UTF_8);
          exchange.sendResponseHeaders(403, body.length);
          exchange.getResponseBody().write(body);
          exchange.close();
        });
    server.createContext(
        "/original",
        exchange -> {
          exchange.getResponseHeaders().set("ETag", "\"v1\"");
          exchange.sendResponseHeaders(304, -1);
          exchange.close();
        });
    server.start();
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort()),
                http,
                false,
                () -> "test-token",
                new JsonCodec())) {
      var problem =
          assertThrows(
              ApiException.class,
              () ->
                  transport.json(
                      "GET",
                      "/problem",
                      null,
                      RequestOptions.defaults(),
                      transport.type(Value.class)));
      assertEquals(403, problem.status());
      assertEquals("ACCESS_DENIED", problem.code());
      assertEquals("native-ref", problem.requestId());
      BinaryResponse file =
          transport.binary(
              "GET", "/original", RequestOptions.defaults().header("If-None-Match", "\"v1\""));
      assertTrue(file.notModified());
      assertEquals(0, file.content().length);
      assertEquals("\"v1\"", file.etag());
    } finally {
      server.stop(0);
    }
  }

  @Test
  void streamsUploadsAndDownloadsWithoutOverwritingFiles(
      @org.junit.jupiter.api.io.TempDir java.nio.file.Path directory) throws Exception {
    var upload = directory.resolve("résumé.txt");
    java.nio.file.Files.writeString(upload, "source content");
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/upload",
        exchange -> {
          assertTrue(
              exchange
                  .getRequestHeaders()
                  .getFirst("Content-Type")
                  .startsWith("multipart/form-data; boundary=koinon-"));
          String request =
              new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
          assertTrue(request.contains("name=\"workspace_id\""));
          assertTrue(request.contains("source content"));
          assertTrue(request.contains("filename=\"résumé.txt\""));
          byte[] body = "{\"name\":\"received\",\"active\":true}".getBytes(StandardCharsets.UTF_8);
          exchange.sendResponseHeaders(201, body.length);
          exchange.getResponseBody().write(body);
          exchange.close();
        });
    server.createContext(
        "/file",
        exchange -> {
          byte[] body = "exact original".getBytes(StandardCharsets.UTF_8);
          exchange
              .getResponseHeaders()
              .set("Content-Disposition", "attachment; filename*=UTF-8''r%C3%A9sum%C3%A9.txt");
          exchange.sendResponseHeaders(200, body.length);
          exchange.getResponseBody().write(body);
          exchange.close();
        });
    server.start();
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort()),
                http,
                false,
                () -> "test-token",
                new JsonCodec())) {
      Value result =
          transport.multipart(
              "POST",
              "/upload",
              upload,
              "file",
              "text/plain",
              Map.of("workspace_id", "workspace1"),
              RequestOptions.defaults(),
              transport.type(Value.class));
      assertEquals("received", result.name());
      var target = directory.resolve("download.txt");
      var downloaded = transport.download("GET", "/file", target, 100, RequestOptions.defaults());
      assertEquals("résumé.txt", downloaded.filename());
      assertEquals("exact original", java.nio.file.Files.readString(target));
      assertThrows(
          IllegalStateException.class,
          () -> transport.download("GET", "/file", target, 100, RequestOptions.defaults()));
      assertEquals("exact original", java.nio.file.Files.readString(target));
      assertThrows(
          IllegalStateException.class,
          () ->
              transport.download(
                  "GET",
                  "/file",
                  directory.resolve("too-large.txt"),
                  2,
                  RequestOptions.defaults()));
      assertFalse(java.nio.file.Files.exists(directory.resolve("too-large.txt")));
      try (var files = java.nio.file.Files.list(directory)) {
        assertFalse(files.anyMatch(file -> file.toString().endsWith(".part")));
      }
    } finally {
      server.stop(0);
    }
  }

  @Test
  void deadlineIncludesReadingBodyAndMutationsAreNotRetried() throws Exception {
    var calls = new AtomicInteger();
    var release = new java.util.concurrent.CountDownLatch(1);
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/slow",
        exchange -> {
          calls.incrementAndGet();
          exchange.sendResponseHeaders(200, 0);
          exchange.getResponseBody().write('{');
          exchange.getResponseBody().flush();
          try {
            release.await(3, TimeUnit.SECONDS);
          } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
          } finally {
            exchange.close();
          }
        });
    server.start();
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort()),
                http,
                false,
                () -> "test-token",
                new JsonCodec())) {
      var task =
          transport.jsonAsync(
              "POST",
              "/slow",
              new Value("once", false),
              RequestOptions.defaults().timeout(Duration.ofMillis(150)),
              transport.type(Value.class));
      var error =
          assertThrows(
              java.util.concurrent.ExecutionException.class, () -> task.get(2, TimeUnit.SECONDS));
      boolean timedOut = false;
      for (Throwable cause = error.getCause(); cause != null; cause = cause.getCause()) {
        if (cause instanceof java.util.concurrent.TimeoutException
            || cause instanceof java.net.http.HttpTimeoutException) timedOut = true;
      }
      assertTrue(timedOut, "The body read must fail with a timeout cause");
      assertEquals(1, calls.get());
    } finally {
      release.countDown();
      server.stop(0);
    }
  }

  @Test
  void validatesPathsRedirectsAndOptionImmutability() {
    assertThrows(IllegalArgumentException.class, () -> Transport.id(".."));
    try (var http = HttpClient.newBuilder().followRedirects(HttpClient.Redirect.ALWAYS).build()) {
      assertThrows(
          IllegalArgumentException.class,
          () ->
              new Transport(
                  URI.create("https://example.test"), http, false, () -> "token", new JsonCodec()));
    }
    assertThrows(
        IllegalArgumentException.class, () -> RequestOptions.defaults().timeout(Duration.ZERO));
    assertThrows(
        IllegalArgumentException.class, () -> RequestOptions.defaults().lastEventId("bad\nvalue"));
    assertThrows(
        IllegalArgumentException.class, () -> RequestOptions.defaults().lastEventId("bad\0value"));
    var original = RequestOptions.defaults();
    var changed = original.idempotencyKey("request1");
    assertEquals(Map.of(), original.headers());
    assertEquals("request1", changed.headers().get("Idempotency-Key"));
    byte[] bytes = {1, 2};
    var binary = new BinaryResponse(bytes, "image/jpeg", null, null, false);
    bytes[0] = 9;
    assertEquals(1, binary.content()[0]);
    binary.content()[0] = 7;
    assertEquals(1, binary.content()[0]);
  }
}
