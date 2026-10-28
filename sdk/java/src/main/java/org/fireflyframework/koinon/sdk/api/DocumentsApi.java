// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class DocumentsApi {
private final Transport transport; private final String prefix;
public DocumentsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public DocumentChunks chunks(String documentId,ChunkFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/documents/"+Transport.id(documentId)+"/chunks",null,options,transport.type(DocumentChunks.class));}
public DocumentChunks chunks(String documentId,ChunkFilter filter){return chunks(documentId,filter,RequestOptions.defaults());}
public DocumentChunks chunks(String documentId){return chunks(documentId,ChunkFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<DocumentChunks> chunksAsync(String documentId,ChunkFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/documents/"+Transport.id(documentId)+"/chunks",null,options,transport.type(DocumentChunks.class));}
public CompletableFuture<DocumentChunks> chunksAsync(String documentId,ChunkFilter filter){return chunksAsync(documentId,filter,RequestOptions.defaults());}
public CompletableFuture<DocumentChunks> chunksAsync(String documentId){return chunksAsync(documentId,ChunkFilter.empty(),RequestOptions.defaults());}
public BinaryResponse original(String documentId,RequestOptions options){Objects.requireNonNull(options);return transport.binary("GET",prefix+"/documents/"+Transport.id(documentId)+"/original",options);}
public BinaryResponse original(String documentId){return original(documentId,RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> originalAsync(String documentId,RequestOptions options){Objects.requireNonNull(options);return transport.binaryAsync("GET",prefix+"/documents/"+Transport.id(documentId)+"/original",options);}
public CompletableFuture<BinaryResponse> originalAsync(String documentId){return originalAsync(documentId,RequestOptions.defaults());}
public FileDownload downloadOriginal(String documentId,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.download("GET",prefix+"/documents/"+Transport.id(documentId)+"/original",target,maxBytes,options);}
public CompletableFuture<FileDownload> downloadOriginalAsync(String documentId,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.downloadAsync("GET",prefix+"/documents/"+Transport.id(documentId)+"/original",target,maxBytes,options);}
public ContentUpdate reingest(String documentId,DocumentReingestInput input,String expectedRevision,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);options=options.ifMatch(ApiSupport.precondition(expectedRevision));return transport.json("POST",prefix+"/documents/"+Transport.id(documentId)+"/reingest",input,options,transport.type(ContentUpdate.class));}
public ContentUpdate reingest(String documentId,DocumentReingestInput input,String expectedRevision){return reingest(documentId,input,expectedRevision,RequestOptions.defaults());}
public CompletableFuture<ContentUpdate> reingestAsync(String documentId,DocumentReingestInput input,String expectedRevision,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);options=options.ifMatch(ApiSupport.precondition(expectedRevision));return transport.jsonAsync("POST",prefix+"/documents/"+Transport.id(documentId)+"/reingest",input,options,transport.type(ContentUpdate.class));}
public CompletableFuture<ContentUpdate> reingestAsync(String documentId,DocumentReingestInput input,String expectedRevision){return reingestAsync(documentId,input,expectedRevision,RequestOptions.defaults());}
public ContentUpdate replace(String documentId,DocumentReplacement input,String expectedRevision,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);options=options.ifMatch(ApiSupport.precondition(expectedRevision));return transport.multipart("POST",prefix+"/documents/"+Transport.id(documentId)+"/content",input.file(),"file",input.mediaType(),ApiSupport.replacementFields(input),options,transport.type(ContentUpdate.class));}
public ContentUpdate replace(String documentId,DocumentReplacement input,String expectedRevision){return replace(documentId,input,expectedRevision,RequestOptions.defaults());}
public CompletableFuture<ContentUpdate> replaceAsync(String documentId,DocumentReplacement input,String expectedRevision,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);options=options.ifMatch(ApiSupport.precondition(expectedRevision));return transport.multipartAsync("POST",prefix+"/documents/"+Transport.id(documentId)+"/content",input.file(),"file",input.mediaType(),ApiSupport.replacementFields(input),options,transport.type(ContentUpdate.class));}
public CompletableFuture<ContentUpdate> replaceAsync(String documentId,DocumentReplacement input,String expectedRevision){return replaceAsync(documentId,input,expectedRevision,RequestOptions.defaults());}
}
