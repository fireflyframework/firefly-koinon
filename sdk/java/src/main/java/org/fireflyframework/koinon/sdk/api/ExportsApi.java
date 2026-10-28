// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ExportsApi {
private final Transport transport; private final String prefix;
public ExportsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ExportReview review(ExportReviewRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/exports/reviews",input,options,transport.type(ExportReview.class));}
public ExportReview review(ExportReviewRequest input){return review(input,RequestOptions.defaults());}
public CompletableFuture<ExportReview> reviewAsync(ExportReviewRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/exports/reviews",input,options,transport.type(ExportReview.class));}
public CompletableFuture<ExportReview> reviewAsync(ExportReviewRequest input){return reviewAsync(input,RequestOptions.defaults());}
public Export create(ExportCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/exports",input,options,transport.type(Export.class));}
public Export create(ExportCreate input){return create(input,RequestOptions.defaults());}
public CompletableFuture<Export> createAsync(ExportCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/exports",input,options,transport.type(Export.class));}
public CompletableFuture<Export> createAsync(ExportCreate input){return createAsync(input,RequestOptions.defaults());}
public ExportPage list(ExportFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/exports",null,options,transport.type(ExportPage.class));}
public ExportPage list(ExportFilter filter){return list(filter,RequestOptions.defaults());}
public ExportPage list(){return list(ExportFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<ExportPage> listAsync(ExportFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/exports",null,options,transport.type(ExportPage.class));}
public CompletableFuture<ExportPage> listAsync(ExportFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<ExportPage> listAsync(){return listAsync(ExportFilter.empty(),RequestOptions.defaults());}
public Export get(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/exports/"+Transport.id(exportId),null,options,transport.type(Export.class));}
public Export get(String exportId){return get(exportId,RequestOptions.defaults());}
public CompletableFuture<Export> getAsync(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/exports/"+Transport.id(exportId),null,options,transport.type(Export.class));}
public CompletableFuture<Export> getAsync(String exportId){return getAsync(exportId,RequestOptions.defaults());}
public BinaryResponse download(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.binary("GET",prefix+"/exports/"+Transport.id(exportId)+"/download",options);}
public BinaryResponse download(String exportId){return download(exportId,RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> downloadAsync(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.binaryAsync("GET",prefix+"/exports/"+Transport.id(exportId)+"/download",options);}
public CompletableFuture<BinaryResponse> downloadAsync(String exportId){return downloadAsync(exportId,RequestOptions.defaults());}
public FileDownload downloadDownload(String exportId,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.download("GET",prefix+"/exports/"+Transport.id(exportId)+"/download",target,maxBytes,options);}
public CompletableFuture<FileDownload> downloadDownloadAsync(String exportId,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.downloadAsync("GET",prefix+"/exports/"+Transport.id(exportId)+"/download",target,maxBytes,options);}
public Void cancel(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/exports/"+Transport.id(exportId),null,options,transport.type(Void.class));}
public Void cancel(String exportId){return cancel(exportId,RequestOptions.defaults());}
public CompletableFuture<Void> cancelAsync(String exportId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/exports/"+Transport.id(exportId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> cancelAsync(String exportId){return cancelAsync(exportId,RequestOptions.defaults());}
}
