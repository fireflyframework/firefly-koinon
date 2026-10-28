// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeApi {
private final Transport transport; private final String prefix;
public KnowledgeApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public SearchResponse search(SearchRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/search",input,options,transport.type(SearchResponse.class));}
public SearchResponse search(SearchRequest input){return search(input,RequestOptions.defaults());}
public CompletableFuture<SearchResponse> searchAsync(SearchRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/search",input,options,transport.type(SearchResponse.class));}
public CompletableFuture<SearchResponse> searchAsync(SearchRequest input){return searchAsync(input,RequestOptions.defaults());}
public QueryResponse query(QueryRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/query",input,options,transport.type(QueryResponse.class));}
public QueryResponse query(QueryRequest input){return query(input,RequestOptions.defaults());}
public CompletableFuture<QueryResponse> queryAsync(QueryRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/query",input,options,transport.type(QueryResponse.class));}
public CompletableFuture<QueryResponse> queryAsync(QueryRequest input){return queryAsync(input,RequestOptions.defaults());}
public Lineage lineage(LineageFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/lineage",null,options,transport.type(Lineage.class));}
public Lineage lineage(LineageFilter filter){return lineage(filter,RequestOptions.defaults());}
public Lineage lineage(){return lineage(LineageFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Lineage> lineageAsync(LineageFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/lineage",null,options,transport.type(Lineage.class));}
public CompletableFuture<Lineage> lineageAsync(LineageFilter filter){return lineageAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Lineage> lineageAsync(){return lineageAsync(LineageFilter.empty(),RequestOptions.defaults());}
}
