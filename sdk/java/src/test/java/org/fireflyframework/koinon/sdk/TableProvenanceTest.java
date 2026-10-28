// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.fireflyframework.koinon.sdk.model.TableProvenanceFilter;
import org.fireflyframework.koinon.sdk.model.TableSnapshotFilter;
import org.junit.jupiter.api.Test;

final class TableProvenanceTest {
  @Test void exactSnapshotAndServerHistoryRemainSeparate() throws Exception {
    var query = new AtomicReference<String>();
    var server = HttpServer.create(new java.net.InetSocketAddress("127.0.0.1", 0), 0);
    server.createContext("/api/v1", exchange -> {
      query.set(exchange.getRequestURI().getRawQuery());
      String unknown = "{\"dataset_id\":\"dataset\",\"table_id\":\"table\",\"native_dataset_id\":\"native-data\",\"native_table_id\":\"native-table\",\"snapshot_id\":\"old/snapshot\",\"status\":\"not_recorded\",\"snapshot_status\":\"READY\",\"level\":\"file_section\"}";
      String value = exchange.getRequestURI().getPath().endsWith("/provenance") ? unknown : "{\"items\":["+unknown+"],\"total\":3,\"page\":2,\"page_size\":1,\"pages\":3,\"has_next\":true,\"has_previous\":true,\"current_snapshot_id\":\"new-snapshot\"}";
      byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, bytes.length);
      exchange.getResponseBody().write(bytes);
      exchange.close();
    });
    server.start();
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:"+server.getAddress().getPort()+"/api/v1")).bearerToken(()->"fresh").build()) {
      var used = client.datasets("north").tableProvenance("data/set", "table/one", TableProvenanceFilter.empty().withSnapshotId("old/snapshot"));
      assertEquals("old/snapshot", used.snapshotId());
      assertEquals("not_recorded", used.status().value());
      assertNull(used.artifact());
      assertTrue(query.get().contains("snapshot_id=old%2Fsnapshot"));
      var page = client.datasets("north").tableSnapshotsAsync("data/set", "table/one", TableSnapshotFilter.empty().withPage(2).withPageSize(1)).join();
      assertEquals("new-snapshot", page.currentSnapshotId());
      assertEquals(3L, page.total());
      assertTrue(query.get().contains("page=2"));
    } finally { server.stop(0); }
  }
}
