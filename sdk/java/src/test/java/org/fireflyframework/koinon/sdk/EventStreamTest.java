// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.junit.jupiter.api.Test;

final class EventStreamTest {
  record WireEvent(String id, String type, JsonNode data) {}

  private static final class Collector implements Flow.Subscriber<WireEvent> {
    final List<WireEvent> events = new CopyOnWriteArrayList<>();
    final CompletableFuture<Void> done = new CompletableFuture<>();
    final boolean cancelFirst;
    Flow.Subscription subscription;

    Collector(boolean cancelFirst) {
      this.cancelFirst = cancelFirst;
    }

    public void onSubscribe(Flow.Subscription value) {
      subscription = value;
      value.request(1);
    }

    public void onNext(WireEvent event) {
      events.add(event);
      if (cancelFirst) {
        subscription.cancel();
        done.complete(null);
      } else subscription.request(1);
    }

    public void onError(Throwable error) {
      done.completeExceptionally(error);
    }

    public void onComplete() {
      done.complete(null);
    }
  }

  @Test
  void parsesUtf8CrLfMultilinePersistentIdsAndIgnoresIncompleteTail() throws Exception {
    var server =
        server(
            "\ufeff: comment\r\n"
                + "id: 9\r\n"
                + "event: result\r\n"
                + "data: {\"text\":\r\n"
                + "data: \"Málaga🧡\"}\r\n\r\n"
                + "id: bad\0value\n"
                + "event: complete\n"
                + "data: {\"ready\":true}\n\n"
                + "event:\ndata: {}\n\n"
                + "data: {\"unfinished\":true}",
            "text/event-stream; charset=utf-8");
    try (var http = HttpClient.newHttpClient();
        var transport = transport(server, http);
        var events =
            transport.stream(
                "/events", RequestOptions.defaults().lastEventId("8"), WireEvent.class)) {
      var subscriber = new Collector(false);
      events.subscribe(subscriber);
      subscriber.done.get(3, TimeUnit.SECONDS);
      assertEquals(3, subscriber.events.size());
      assertEquals("9", subscriber.events.get(0).id());
      assertEquals("result", subscriber.events.get(0).type());
      assertEquals("Málaga🧡", subscriber.events.get(0).data().path("text").asText());
      assertEquals("9", subscriber.events.get(1).id());
      assertEquals("complete", subscriber.events.get(1).type());
      assertEquals("message", subscriber.events.get(2).type());
    } finally {
      server.stop(0);
    }
  }

  @Test
  void cancellationPreventsSubsequentEventsAndRejectsSecondSubscriber() throws Exception {
    var server = server("id: 1\ndata: {}\n\nid: 2\ndata: {}\n\n", "text/event-stream");
    try (var http = HttpClient.newHttpClient();
        var transport = transport(server, http);
        var events = transport.stream("/events", RequestOptions.defaults(), WireEvent.class)) {
      var subscriber = new Collector(true);
      events.subscribe(subscriber);
      subscriber.done.get(3, TimeUnit.SECONDS);
      assertEquals(1, subscriber.events.size());
      var second = new Collector(false);
      events.subscribe(second);
      assertThrows(
          java.util.concurrent.ExecutionException.class,
          () -> second.done.get(3, TimeUnit.SECONDS));
    } finally {
      server.stop(0);
    }
  }

  @Test
  void rejectsWrongMimeAndOversizedFrames() throws Exception {
    for (var content :
        List.of(
            "{}",
            "data: " + "a".repeat(1_048_577) + "\n\n",
            "data: " + "💡".repeat(300_000) + "\n\n")) {
      var server = server(content, content.equals("{}") ? "application/json" : "text/event-stream");
      try (var http = HttpClient.newHttpClient();
          var transport = transport(server, http);
          var events = transport.stream("/events", RequestOptions.defaults(), WireEvent.class)) {
        var subscriber = new Collector(false);
        events.subscribe(subscriber);
        var error =
            assertThrows(
                java.util.concurrent.ExecutionException.class,
                () -> subscriber.done.get(4, TimeUnit.SECONDS));
        assertTrue(
            error
                .getCause()
                .getMessage()
                .contains(content.equals("{}") ? "text/event-stream" : "1 MiB"));
        assertTrue(subscriber.events.isEmpty());
      } finally {
        server.stop(0);
      }
    }
  }

  @Test
  void obtainsCurrentCredentialsOnlyWhenTheStreamIsConsumed() throws Exception {
    var calls = new java.util.concurrent.atomic.AtomicInteger();
    var server = server("data: {}\n\n", "text/event-stream");
    try (var http = HttpClient.newHttpClient();
        var transport =
            new Transport(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort()),
                http,
                false,
                () -> "token-" + calls.incrementAndGet(),
                new JsonCodec());
        var events = transport.stream("/events", RequestOptions.defaults(), WireEvent.class)) {
      assertEquals(0, calls.get());
      var subscriber = new Collector(false);
      events.subscribe(subscriber);
      subscriber.done.get(3, TimeUnit.SECONDS);
      assertEquals(1, calls.get());
    } finally {
      server.stop(0);
    }
  }

  private static Transport transport(HttpServer server, HttpClient http) {
    return new Transport(
        URI.create("http://127.0.0.1:" + server.getAddress().getPort()),
        http,
        false,
        () -> "fictional-token",
        new JsonCodec());
  }

  private static HttpServer server(String content, String mime) throws Exception {
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext(
        "/events",
        exchange -> {
          exchange.getResponseHeaders().set("Content-Type", mime);
          exchange.sendResponseHeaders(200, 0);
          byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
          try {
            for (int offset = 0; offset < bytes.length; offset += 71) {
              exchange.getResponseBody().write(bytes, offset, Math.min(71, bytes.length - offset));
              exchange.getResponseBody().flush();
            }
          } catch (java.io.IOException ignored) {
            /* Expected when the subscriber cancels. */
          } finally {
            exchange.close();
          }
        });
    server.start();
    return server;
  }
}
