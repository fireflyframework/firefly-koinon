// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.PushbackReader;
import java.net.http.HttpResponse;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Flow;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Supplier;
import org.fireflyframework.koinon.sdk.internal.Blocking;
import org.fireflyframework.koinon.sdk.internal.JsonCodec;

/** One-subscriber, demand-aware SSE connection. Cancel or close it to release the HTTP body. */
public final class EventStream<T> implements Flow.Publisher<T>, AutoCloseable {
  private static final int FRAME_LIMIT = 1_048_576;

  @FunctionalInterface
  public interface ProblemReader {
    ApiException read(HttpResponse<InputStream> response) throws IOException;
  }

  private final Supplier<CompletableFuture<HttpResponse<InputStream>>> open;
  private final JsonCodec codec;
  private final Class<T> eventType;
  private final ProblemReader problem;
  private final AtomicBoolean subscribed = new AtomicBoolean();
  private final Object demandLock = new Object();
  private volatile CompletableFuture<?> opening;
  private volatile InputStream input;
  private volatile boolean closed;
  private volatile Throwable failure;
  private Runnable cleanup = () -> {};
  private long demand;

  public EventStream(
      Supplier<CompletableFuture<HttpResponse<InputStream>>> open,
      JsonCodec codec,
      Class<T> eventType,
      ProblemReader problem) {
    this.open = open;
    this.codec = codec;
    this.eventType = eventType;
    this.problem = problem;
  }

  /** Used by the owning transport to track open connections. */
  public synchronized void onClose(Runnable cleanup) {
    this.cleanup = Objects.requireNonNull(cleanup);
    if (closed) cleanup.run();
  }

  @Override
  public void subscribe(Flow.Subscriber<? super T> subscriber) {
    Objects.requireNonNull(subscriber);
    if (!subscribed.compareAndSet(false, true)) {
      subscriber.onSubscribe(
          new Flow.Subscription() {
            public void request(long n) {}

            public void cancel() {}
          });
      subscriber.onError(new IllegalStateException("An event stream supports one subscriber"));
      return;
    }
    subscriber.onSubscribe(
        new Flow.Subscription() {
          @Override
          public void request(long count) {
            synchronized (demandLock) {
              if (closed) return;
              if (count <= 0) {
                failure = new IllegalArgumentException("Stream demand must be positive");
                closeInput();
              } else demand = count > Long.MAX_VALUE - demand ? Long.MAX_VALUE : demand + count;
              demandLock.notifyAll();
            }
          }

          @Override
          public void cancel() {
            close();
          }
        });
    Thread.ofVirtual().name("koinon-events").start(() -> consume(subscriber));
  }

  private void consume(Flow.Subscriber<? super T> subscriber) {
    try {
      if (closed) return;
      var responseTask = open.get();
      opening = responseTask;
      if (closed) {
        responseTask.cancel(true);
        return;
      }
      var response = Blocking.await(responseTask);
      input = response.body();
      if (closed) {
        closeInput();
        return;
      }
      if (response.statusCode() >= 300) throw problem.read(response);
      if (!response
          .headers()
          .firstValue("Content-Type")
          .orElse("")
          .split(";", 2)[0]
          .trim()
          .equalsIgnoreCase("text/event-stream"))
        throw new IOException("Expected a text/event-stream response");
      var decoder =
          StandardCharsets.UTF_8
              .newDecoder()
              .onMalformedInput(CodingErrorAction.REPORT)
              .onUnmappableCharacter(CodingErrorAction.REPORT);
      try (var reader = new PushbackReader(new InputStreamReader(input, decoder), 1)) {
        String id = "", kind = "message";
        var data = new StringBuilder();
        int frameBytes = 0;
        boolean first = true;
        while (!closed) {
          awaitDemand();
          if (closed) break;
          if (failure != null) throw new IOException("Invalid stream demand", failure);
          String line = line(reader);
          if (line == null) break;
          if (first && line.startsWith("\ufeff")) line = line.substring(1);
          first = false;
          frameBytes += line.getBytes(StandardCharsets.UTF_8).length + 1;
          if (frameBytes > FRAME_LIMIT) throw new IOException("Event stream frame exceeds 1 MiB");
          if (line.isEmpty()) {
            if (!data.isEmpty()) {
              T event = codec.event(id, kind, data.substring(0, data.length() - 1), eventType);
              synchronized (demandLock) {
                if (demand != Long.MAX_VALUE) demand--;
              }
              if (!closed) subscriber.onNext(event);
            }
            kind = "message";
            data.setLength(0);
            frameBytes = 0;
          } else if (!line.startsWith(":")) {
            int colon = line.indexOf(':');
            String field = colon < 0 ? line : line.substring(0, colon),
                value = colon < 0 ? "" : line.substring(colon + 1);
            if (value.startsWith(" ")) value = value.substring(1);
            switch (field) {
              case "data" -> data.append(value).append('\n');
              case "event" -> kind = value.isEmpty() ? "message" : value;
              case "id" -> {
                if (value.indexOf('\0') < 0) id = value;
              }
              default -> {}
            }
          }
        }
      }
      if (!closed) {
        if (failure != null) subscriber.onError(failure);
        else subscriber.onComplete();
      }
    } catch (Exception error) {
      if (!closed) subscriber.onError(failure == null ? error : failure);
    } finally {
      close();
    }
  }

  private void awaitDemand() throws InterruptedException {
    synchronized (demandLock) {
      while (demand == 0 && !closed && failure == null) demandLock.wait();
    }
  }

  private static String line(PushbackReader reader) throws IOException {
    var result = new StringBuilder();
    int value;
    while ((value = reader.read()) != -1) {
      if (value == '\n') return result.toString();
      if (value == '\r') {
        int next = reader.read();
        if (next != -1 && next != '\n') reader.unread(next);
        return result.toString();
      }
      result.append((char) value);
      if (result.length() > FRAME_LIMIT) throw new IOException("Event stream line exceeds 1 MiB");
    }
    return result.isEmpty() ? null : result.toString();
  }

  private void closeInput() {
    var body = input;
    if (body != null)
      try {
        body.close();
      } catch (IOException ignored) {
        /* Cancellation owns this close. */
      }
  }

  @Override
  public void close() {
    Runnable done;
    synchronized (this) {
      if (closed) return;
      closed = true;
      done = cleanup;
    }
    var task = opening;
    if (task != null && !task.isDone()) task.cancel(true);
    closeInput();
    synchronized (demandLock) {
      demandLock.notifyAll();
    }
    done.run();
  }
}
