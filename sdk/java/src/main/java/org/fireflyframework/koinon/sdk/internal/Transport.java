// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.JsonNode;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Supplier;
import org.fireflyframework.koinon.sdk.ApiException;
import org.fireflyframework.koinon.sdk.BinaryResponse;
import org.fireflyframework.koinon.sdk.EventStream;
import org.fireflyframework.koinon.sdk.FileDownload;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.BulkFilePath;

/** Implementation detail shared by the typed resource groups. */
public final class Transport implements AutoCloseable {
  static final int JSON_LIMIT = 8 * 1024 * 1024;
  static final int BINARY_LIMIT = 64 * 1024 * 1024;
  private final URI base;
  private final HttpClient http;
  private final JsonCodec codec;
  private final Supplier<String> bearer;
  private final boolean ownsClient;
  private final Set<CompletableFuture<?>> requests;
  private final Set<AutoCloseable> streams;
  private final AtomicBoolean closed;
  private final boolean view;

  public Transport(
      URI base, HttpClient http, boolean ownsClient, Supplier<String> bearer, JsonCodec codec) {
    validate(base);
    this.base = URI.create(base.toASCIIString().replaceAll("/+$", "") + "/");
    this.http = Objects.requireNonNull(http);
    this.ownsClient = ownsClient;
    this.bearer = bearer;
    this.codec = codec;
    requests = ConcurrentHashMap.newKeySet();
    streams = ConcurrentHashMap.newKeySet();
    closed = new AtomicBoolean();
    view = false;
    if (http.followRedirects() != HttpClient.Redirect.NEVER)
      throw new IllegalArgumentException("The SDK HTTP client must disable redirects");
  }

  private Transport(Transport parent) {
    base = URI.create(parent.base.getScheme() + "://" + parent.base.getRawAuthority() + "/");
    http = parent.http;
    ownsClient = false;
    bearer = parent.bearer;
    codec = parent.codec;
    requests = parent.requests;
    streams = parent.streams;
    closed = parent.closed;
    view = true;
  }

  public Transport atOrigin() {
    return base.getPath().equals("/") ? this : new Transport(this);
  }

  public static void validate(URI uri) {
    if (uri == null
        || uri.getHost() == null
        || !("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))
        || uri.getRawUserInfo() != null
        || uri.getRawQuery() != null
        || uri.getRawFragment() != null)
      throw new IllegalArgumentException(
          "Use an absolute HTTP API address without credentials, query or fragment");
  }

  public static String id(String value) {
    if (value == null || value.isBlank() || value.equals(".") || value.equals(".."))
      throw new IllegalArgumentException("Provide a resource identifier");
    return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
  }

  public JavaType type(Class<?> type) {
    return codec.type(type);
  }

  public JavaType pageType(Class<?> itemType) {
    return codec
        .mapper
        .getTypeFactory()
        .constructParametricType(org.fireflyframework.koinon.sdk.model.Page.class, itemType);
  }

  HttpRequest request(
      String method,
      String path,
      HttpRequest.BodyPublisher body,
      RequestOptions options,
      String contentType,
      String accept) {
    if (closed.get()) throw new IllegalStateException("The SDK client is closed");
    if (!path.startsWith("/") || path.startsWith("//") || path.contains("?") || path.contains("#"))
      throw new IllegalArgumentException("Use a relative API operation path");
    for (String segment : path.split("/")) {
      String decoded = URLDecoder.decode(segment, StandardCharsets.UTF_8);
      if (decoded.equals(".") || decoded.equals(".."))
        throw new IllegalArgumentException("Resource paths cannot contain traversal segments");
    }
    var target = new StringBuilder(base.toASCIIString()).append(path.substring(1));
    for (var entry : options.query().entrySet())
      target
          .append(target.indexOf("?") < 0 ? '?' : '&')
          .append(URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8))
          .append('=')
          .append(URLEncoder.encode(entry.getValue(), StandardCharsets.UTF_8));
    var builder =
        HttpRequest.newBuilder(URI.create(target.toString()))
            .timeout(options.timeout())
            .header("Accept", accept);
    String token = bearer == null ? null : bearer.get();
    if (token != null && !token.isBlank()) builder.header("Authorization", "Bearer " + token);
    if (contentType != null) builder.header("Content-Type", contentType);
    options.headers().forEach(builder::setHeader);
    return builder.method(method, body).build();
  }

  public <T> T json(
      String method, String path, Object body, RequestOptions options, JavaType type) {
    return Blocking.await(jsonAsync(method, path, body, options, type));
  }

  public <T> CompletableFuture<T> jsonAsync(
      String method, String path, Object body, RequestOptions options, JavaType type) {
    return typed(
        request(
            method,
            path,
            body == null
                ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofByteArray(codec.encode(body)),
            options,
            body == null ? null : "application/json",
            "application/json"),
        options,
        type);
  }

  public <T> T bytes(
      String method,
      String path,
      byte[] body,
      String mediaType,
      RequestOptions options,
      JavaType type) {
    return Blocking.await(bytesAsync(method, path, body, mediaType, options, type));
  }

  public <T> T file(
      String method, String path, BulkFilePath original, RequestOptions options, JavaType type) {
    return Blocking.await(fileAsync(method, path, original, options, type));
  }

  public <T> CompletableFuture<T> fileAsync(
      String method, String path, BulkFilePath original, RequestOptions options, JavaType type) {
    var snapshot = original.snapshot();
    try {
      CompletableFuture<T> result = typed(
          request(method, path, snapshot.publisher(), options, "application/octet-stream", "application/json"),
          options, type);
      result.whenComplete((value, error) -> snapshot.close());
      return result;
    } catch (IOException error) {
      snapshot.close();
      return CompletableFuture.failedFuture(error);
    } catch (RuntimeException error) {
      snapshot.close();
      throw error;
    }
  }

  public <T> CompletableFuture<T> bytesAsync(
      String method,
      String path,
      byte[] body,
      String mediaType,
      RequestOptions options,
      JavaType type) {
    return typed(
        request(
            method,
            path,
            HttpRequest.BodyPublishers.ofByteArray(body),
            options,
            mediaType,
            "application/json"),
        options,
        type);
  }

  private <T> CompletableFuture<T> typed(
      HttpRequest request, RequestOptions options, JavaType type) {
    return exchange(
        request,
        options,
        response -> {
          byte[] bytes = bounded(response.body(), JSON_LIMIT);
          if (response.statusCode() >= 300)
            throw problem(
                response.statusCode(),
                bytes,
                response.headers().firstValue("X-Request-ID").orElse(null));
          if (type.getRawClass() == Void.class || response.statusCode() == 204) return null;
          return codec.decode(bytes, type);
        });
  }

  public BinaryResponse binary(String method, String path, RequestOptions options) {
    return Blocking.await(binaryAsync(method, path, options));
  }

  public CompletableFuture<BinaryResponse> binaryAsync(
      String method, String path, RequestOptions options) {
    var request = request(method, path, HttpRequest.BodyPublishers.noBody(), options, null, "*/*");
    return exchange(
        request,
        options,
        response -> {
          if (response.statusCode() >= 300 && response.statusCode() != 304)
            throw problem(
                response.statusCode(),
                bounded(response.body(), JSON_LIMIT),
                response.headers().firstValue("X-Request-ID").orElse(null));
          return new BinaryResponse(
              response.statusCode() == 304 ? new byte[0] : bounded(response.body(), BINARY_LIMIT),
              response.headers().firstValue("Content-Type").orElse(null),
              response.headers().firstValue("ETag").orElse(null),
              filename(response.headers().firstValue("Content-Disposition").orElse(null)),
              response.statusCode() == 304);
        });
  }

  public FileDownload download(
      String method, String path, Path target, long maxBytes, RequestOptions options) {
    return Blocking.await(downloadAsync(method, path, target, maxBytes, options));
  }

  public CompletableFuture<FileDownload> downloadAsync(
      String method, String path, Path target, long maxBytes, RequestOptions options) {
    if (maxBytes < 1) throw new IllegalArgumentException("Download byte limit must be positive");
    var destination = target.toAbsolutePath().normalize();
    var request = request(method, path, HttpRequest.BodyPublishers.noBody(), options, null, "*/*");
    return exchange(
        request,
        options,
        response -> {
          String mime = response.headers().firstValue("Content-Type").orElse(null),
              etag = response.headers().firstValue("ETag").orElse(null);
          String name = filename(response.headers().firstValue("Content-Disposition").orElse(null));
          if (response.statusCode() == 304)
            return new FileDownload(destination, 0, mime, etag, name, true);
          if (response.statusCode() >= 300)
            throw problem(
                response.statusCode(),
                bounded(response.body(), JSON_LIMIT),
                response.headers().firstValue("X-Request-ID").orElse(null));
          if (Files.exists(destination))
            throw new FileAlreadyExistsException(destination.toString());
          var temporary =
              Files.createTempFile(destination.getParent(), ".koinon-download-", ".part");
          try {
            long total = 0;
            try (var output = Files.newOutputStream(temporary)) {
              byte[] chunk = new byte[64 * 1024];
              int count;
              while ((count = response.body().read(chunk)) != -1) {
                if (count > maxBytes - total)
                  throw new IOException("Download exceeded the configured byte limit");
                output.write(chunk, 0, count);
                total += count;
              }
            }
            Files.move(temporary, destination);
            return new FileDownload(destination, total, mime, etag, name, false);
          } finally {
            Files.deleteIfExists(temporary);
          }
        });
  }

  public <T> T multipart(
      String method,
      String path,
      Path file,
      String fieldName,
      String mediaType,
      Map<String, String> fields,
      RequestOptions options,
      JavaType type) {
    return Blocking.await(
        multipartAsync(method, path, file, fieldName, mediaType, fields, options, type));
  }

  public <T> CompletableFuture<T> multipartAsync(
      String method,
      String path,
      Path file,
      String fieldName,
      String mediaType,
      Map<String, String> fields,
      RequestOptions options,
      JavaType type) {
    String boundary = "koinon-" + UUID.randomUUID();
    var parts = new ArrayList<HttpRequest.BodyPublisher>();
    fields.forEach(
        (name, value) ->
            parts.add(
                HttpRequest.BodyPublishers.ofString(
                    "--"
                        + boundary
                        + "\r\nContent-Disposition: form-data; name=\""
                        + quoted(name)
                        + "\"\r\n\r\n"
                        + value
                        + "\r\n",
                    StandardCharsets.UTF_8)));
    parts.add(
        HttpRequest.BodyPublishers.ofString(
            "--"
                + boundary
                + "\r\nContent-Disposition: form-data; name=\""
                + quoted(fieldName)
                + "\"; filename=\""
                + quoted(file.getFileName().toString())
                + "\"\r\nContent-Type: "
                + mediaType
                + "\r\n\r\n",
            StandardCharsets.UTF_8));
    try {
      parts.add(HttpRequest.BodyPublishers.ofFile(file));
    } catch (IOException error) {
      return CompletableFuture.failedFuture(error);
    }
    parts.add(HttpRequest.BodyPublishers.ofString("\r\n--" + boundary + "--\r\n"));
    if (mediaType.indexOf('\r') >= 0 || mediaType.indexOf('\n') >= 0)
      throw new IllegalArgumentException("Invalid media type");
    return typed(
        request(
            method,
            path,
            HttpRequest.BodyPublishers.concat(parts.toArray(HttpRequest.BodyPublisher[]::new)),
            options,
            "multipart/form-data; boundary=" + boundary,
            "application/json"),
        options,
        type);
  }

  public <T> EventStream<T> stream(String path, RequestOptions options, Class<T> eventType) {
    if (closed.get()) throw new IllegalStateException("The SDK client is closed");
    var events =
        new EventStream<T>(
            () ->
                http.sendAsync(
                    request(
                        "GET",
                        path,
                        HttpRequest.BodyPublishers.noBody(),
                        options,
                        null,
                        "text/event-stream"),
                    HttpResponse.BodyHandlers.ofInputStream()),
            codec,
            eventType,
            this::streamProblem);
    streams.add(events);
    events.onClose(() -> streams.remove(events));
    if (closed.get()) events.close();
    return events;
  }

  private ApiException streamProblem(HttpResponse<InputStream> response) throws IOException {
    return problem(
        response.statusCode(),
        bounded(response.body(), JSON_LIMIT),
        response.headers().firstValue("X-Request-ID").orElse(null));
  }

  @FunctionalInterface
  private interface Reader<T> {
    T read(HttpResponse<InputStream> response) throws IOException;
  }

  private <T> CompletableFuture<T> exchange(
      HttpRequest request, RequestOptions options, Reader<T> reader) {
    var source = http.sendAsync(request, HttpResponse.BodyHandlers.ofInputStream());
    var body = new AtomicReference<InputStream>();
    var result = new CompletableFuture<T>();
    requests.add(result);
    result.orTimeout(options.timeout().toMillis(), TimeUnit.MILLISECONDS);
    result.whenComplete(
        (value, error) -> {
          requests.remove(result);
          if (error != null) source.cancel(true);
          closeQuietly(body.getAndSet(null));
        });
    source.whenComplete(
        (response, error) -> {
          if (error != null) {
            result.completeExceptionally(error);
            return;
          }
          body.set(response.body());
          if (result.isDone()) {
            closeQuietly(body.getAndSet(null));
            return;
          }
          Thread.ofVirtual()
              .start(
                  () -> {
                    try {
                      result.complete(reader.read(response));
                    } catch (Exception problem) {
                      result.completeExceptionally(problem);
                    } finally {
                      closeQuietly(body.getAndSet(null));
                    }
                  });
        });
    if (closed.get()) result.cancel(true);
    return result;
  }

  static byte[] bounded(InputStream input, int limit) throws IOException {
    byte[] bytes = input.readNBytes(limit + 1);
    if (bytes.length > limit)
      throw new IOException("API response exceeded the configured byte limit");
    return bytes;
  }

  ApiException problem(int status, byte[] content, String requestId) {
    String code = "HTTP_" + status, message = "API request failed (HTTP " + status + ")";
    try {
      JsonNode value = codec.tree(content);
      JsonNode legacy = value.path("error");
      code = text(value, "code", text(value, "errorCode", text(legacy, "code", code)));
      message =
          text(
              value,
              "detail",
              text(value, "message", text(legacy, "message", text(value, "title", message))));
      requestId =
          text(
              value,
              "transactionId",
              text(
                  value,
                  "requestId",
                  text(value, "transaction_id", text(legacy, "transaction_id", requestId))));
    } catch (IOException ignored) {
      /* Non-JSON proxy errors still retain their HTTP status. */
    }
    return new ApiException(status, code, message, requestId);
  }

  private static String quoted(String value) {
    if (value == null || value.isBlank() || value.chars().anyMatch(c -> c < 32 || c == 127))
      throw new IllegalArgumentException("Invalid multipart field or filename");
    return value.replace("\\", "\\\\").replace("\"", "\\\"");
  }

  private static String filename(String value) {
    if (value == null) return null;
    var utf = java.util.regex.Pattern.compile("(?i)filename\\*=UTF-8''([^;]+)").matcher(value);
    if (utf.find())
      try {
        return URLDecoder.decode(utf.group(1), StandardCharsets.UTF_8);
      } catch (IllegalArgumentException ignored) {
        return null;
      }
    var plain =
        java.util.regex.Pattern.compile("(?i)filename=\"([^\"]*)\"|filename=([^;]+)")
            .matcher(value);
    return plain.find() ? (plain.group(1) == null ? plain.group(2).trim() : plain.group(1)) : null;
  }

  private static String text(JsonNode node, String key, String fallback) {
    var value = node.path(key);
    return value.isTextual() ? value.textValue() : fallback;
  }

  static void closeQuietly(AutoCloseable resource) {
    if (resource != null)
      try {
        resource.close();
      } catch (Exception ignored) {
        /* Closing must not mask the request failure. */
      }
  }

  @Override
  public void close() {
    if (view || !closed.compareAndSet(false, true)) return;
    streams.forEach(Transport::closeQuietly);
    requests.forEach(task -> task.cancel(true));
    if (ownsClient) http.close();
  }
}
