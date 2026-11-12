// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;
import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.fireflyframework.koinon.sdk.model.CatalogBrowseInput;
import org.fireflyframework.koinon.sdk.model.SearchRequest;
import org.fireflyframework.koinon.sdk.model.HistoryBrowseInput;
import org.fireflyframework.koinon.sdk.model.MessageBrowseInput;
import org.fireflyframework.koinon.sdk.model.ShareBrowseInput;
import org.junit.jupiter.api.Test;

final class ReaderSourcesTest {
  @Test
  void readerChoicesKeepOmittedNullAndEmptyDistinctOnActualHttp() throws Exception {
    var bodies = new ArrayList<String>();
    var tokens = new ArrayList<String>();
    var paths = new ArrayList<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      tokens.add(exchange.getRequestHeaders().getFirst("Authorization"));
      paths.add(exchange.getRequestURI().getPath());
      var content = exchange.getRequestURI().getPath().endsWith("/browse")
          ? "{\"items\":[],\"actors\":{},\"next_cursor\":null,\"total\":null,\"total_is_exact\":false}"
          : "{\"hits\":[],\"answer\":null}";
      var response = content.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, response.length);
      exchange.getResponseBody().write(response);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"
        + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "reader").build()) {
      var request = SearchRequest.empty().withQuestion("Q");
      client.knowledge("north").search(request);
      client.knowledge("north").search(request.withReaderSourceConnections(List.of()));
      client.knowledge("north").search(request.clearReaderSourceConnections());
      var page = client.catalog("north").browse(CatalogBrowseInput.empty().withReaderSourceConnections(List.of()));
      var history = client.chat("north").browse(HistoryBrowseInput.empty().withReaderSourceConnections(List.of()));
      var messages = client.chat("north").browseMessages("thread", MessageBrowseInput.empty().withReaderSourceConnections(List.of()));
      var shares = client.shares("north").browse(ShareBrowseInput.empty().withReaderSourceConnections(List.of()));
      assertFalse(bodies.get(0).contains("reader_source_connections"));
      assertTrue(bodies.get(1).contains("\"reader_source_connections\":[]"));
      assertTrue(bodies.get(2).contains("\"reader_source_connections\":null"));
      assertTrue(bodies.get(3).contains("\"reader_source_connections\":[]"));
      assertFalse(page.totalIsExact());
      assertTrue(page.total() == null || page.total().isNull());
      assertFalse(history.totalIsExact());
      assertFalse(messages.totalIsExact());
      assertFalse(shares.totalIsExact());
      assertEquals("/api/v1/tenants/north/chat/threads/browse", paths.get(4));
      assertEquals("/api/v1/tenants/north/chat/threads/thread/messages/browse", paths.get(5));
      assertEquals("/api/v1/tenants/north/shares/browse", paths.get(6));
      assertEquals(7, tokens.size());
      assertTrue(tokens.stream().allMatch("Bearer reader"::equals));
    } finally {
      server.stop(0);
    }
  }
  @Test
  void binaryReaderPostCarriesLocalOnlyBody(@org.junit.jupiter.api.io.TempDir java.nio.file.Path directory) throws Exception {
    var bodies = new ArrayList<String>();
    var methods = new ArrayList<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1/tenants/north/documents/doc/original/read", exchange -> {
      bodies.add(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
      methods.add(exchange.getRequestMethod());
      byte[] bytes = "original".getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/pdf");
      exchange.getResponseHeaders().set("Content-Disposition", "attachment; filename=source.pdf");
      exchange.sendResponseHeaders(200, bytes.length);
      exchange.getResponseBody().write(bytes);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:" + server.getAddress().getPort() + "/api/v1")).bearerToken(() -> "reader").build()) {
      var result = client.documents("north").readOriginal("doc", org.fireflyframework.koinon.sdk.model.ReaderReadInput.empty().withReaderSourceConnections(List.of()));
      var file = client.documents("north").downloadReadOriginal("doc", org.fireflyframework.koinon.sdk.model.ReaderReadInput.empty().withReaderSourceConnections(List.of()), directory.resolve("original.pdf"), 1024, RequestOptions.defaults());
      assertArrayEquals("original".getBytes(StandardCharsets.UTF_8), java.nio.file.Files.readAllBytes(file.path()));
      assertEquals(List.of("POST", "POST"), methods);
      assertEquals(List.of("{\"reader_source_connections\":[]}", "{\"reader_source_connections\":[]}"), bodies);
      assertEquals("source.pdf", result.filename());
      assertArrayEquals("original".getBytes(StandardCharsets.UTF_8), result.content());
    } finally { server.stop(0); }
  }

}
