// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.GlossaryPage;
import org.fireflyframework.koinon.sdk.model.GlossaryTermCreate;
import org.fireflyframework.koinon.sdk.model.GlossaryTermRead;
import org.fireflyframework.koinon.sdk.model.GlossaryTermUpdate;

/** Qualified retained glossary writes; preserve the exact returned revision timestamp. */
public final class StructuredGlossaryApi {
  private final Transport transport;
  private final String tenant, workspace, prefix;

  public StructuredGlossaryApi(Transport transport, String tenant, String workspace, boolean agent) {
    this.transport = Objects.requireNonNull(transport);
    this.tenant = Objects.requireNonNull(tenant);
    this.workspace = Objects.requireNonNull(workspace);
    this.prefix = "/structured/" + (agent ? "agent/" : "") + "glossary";
  }
  private RequestOptions scoped(RequestOptions options) {
    return options.header("X-Tenant-ID", tenant).header("X-Workspace-ID", workspace);
  }
  public GlossaryPage list(int limit, int offset, RequestOptions options) { return transport.json("GET", prefix, null, scoped(options).query("limit", limit).query("offset", offset), transport.type(GlossaryPage.class)); }
  public GlossaryPage list(int limit, int offset) { return list(limit, offset, RequestOptions.defaults()); }
  public GlossaryPage list() { return list(100, 0); }
  public CompletableFuture<GlossaryPage> listAsync(int limit, int offset, RequestOptions options) { return transport.jsonAsync("GET", prefix, null, scoped(options).query("limit", limit).query("offset", offset), transport.type(GlossaryPage.class)); }
  public CompletableFuture<GlossaryPage> listAsync(int limit, int offset) { return listAsync(limit, offset, RequestOptions.defaults()); }
  public CompletableFuture<GlossaryPage> listAsync() { return listAsync(100, 0); }
  public GlossaryTermRead get(String termId, RequestOptions options) { return transport.json("GET", prefix + "/" + Transport.id(termId), null, scoped(options), transport.type(GlossaryTermRead.class)); }
  public GlossaryTermRead get(String termId) { return get(termId, RequestOptions.defaults()); }
  public CompletableFuture<GlossaryTermRead> getAsync(String termId, RequestOptions options) { return transport.jsonAsync("GET", prefix + "/" + Transport.id(termId), null, scoped(options), transport.type(GlossaryTermRead.class)); }
  public CompletableFuture<GlossaryTermRead> getAsync(String termId) { return getAsync(termId, RequestOptions.defaults()); }

  public GlossaryTermRead create(GlossaryTermCreate input, RequestOptions options) {
    return transport.json("POST", prefix, Objects.requireNonNull(input), scoped(options), transport.type(GlossaryTermRead.class));
  }
  public GlossaryTermRead create(GlossaryTermCreate input) { return create(input, RequestOptions.defaults()); }
  public CompletableFuture<GlossaryTermRead> createAsync(GlossaryTermCreate input, RequestOptions options) {
    return transport.jsonAsync("POST", prefix, Objects.requireNonNull(input), scoped(options), transport.type(GlossaryTermRead.class));
  }
  public CompletableFuture<GlossaryTermRead> createAsync(GlossaryTermCreate input) { return createAsync(input, RequestOptions.defaults()); }
  public GlossaryTermRead update(String termId, GlossaryTermUpdate input, String expectedUpdatedAt, RequestOptions options) {
    return transport.json("PUT", prefix + "/" + Transport.id(termId), Objects.requireNonNull(input), scoped(options).ifMatch(ApiSupport.precondition(expectedUpdatedAt)), transport.type(GlossaryTermRead.class));
  }
  public GlossaryTermRead update(String termId, GlossaryTermUpdate input, String expectedUpdatedAt) { return update(termId, input, expectedUpdatedAt, RequestOptions.defaults()); }
  public CompletableFuture<GlossaryTermRead> updateAsync(String termId, GlossaryTermUpdate input, String expectedUpdatedAt, RequestOptions options) {
    return transport.jsonAsync("PUT", prefix + "/" + Transport.id(termId), Objects.requireNonNull(input), scoped(options).ifMatch(ApiSupport.precondition(expectedUpdatedAt)), transport.type(GlossaryTermRead.class));
  }
  public CompletableFuture<GlossaryTermRead> updateAsync(String termId, GlossaryTermUpdate input, String expectedUpdatedAt) { return updateAsync(termId, input, expectedUpdatedAt, RequestOptions.defaults()); }
  public Void remove(String termId, String expectedUpdatedAt, RequestOptions options) {
    return transport.json("DELETE", prefix + "/" + Transport.id(termId), null, scoped(options).ifMatch(ApiSupport.precondition(expectedUpdatedAt)), transport.type(Void.class));
  }
  public Void remove(String termId, String expectedUpdatedAt) { return remove(termId, expectedUpdatedAt, RequestOptions.defaults()); }
  public CompletableFuture<Void> removeAsync(String termId, String expectedUpdatedAt, RequestOptions options) {
    return transport.jsonAsync("DELETE", prefix + "/" + Transport.id(termId), null, scoped(options).ifMatch(ApiSupport.precondition(expectedUpdatedAt)), transport.type(Void.class));
  }
  public CompletableFuture<Void> removeAsync(String termId, String expectedUpdatedAt) { return removeAsync(termId, expectedUpdatedAt, RequestOptions.defaults()); }
}
