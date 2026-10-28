// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class SourcesApi {
private final Transport transport; private final String prefix;
public SourcesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public UploadResponse upload(SourceUpload input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.multipart("POST",prefix+"/sources/upload",input.file(),"file",input.mediaType(),ApiSupport.uploadFields(input),options,transport.type(UploadResponse.class));}
public UploadResponse upload(SourceUpload input){return upload(input,RequestOptions.defaults());}
public CompletableFuture<UploadResponse> uploadAsync(SourceUpload input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.multipartAsync("POST",prefix+"/sources/upload",input.file(),"file",input.mediaType(),ApiSupport.uploadFields(input),options,transport.type(UploadResponse.class));}
public CompletableFuture<UploadResponse> uploadAsync(SourceUpload input){return uploadAsync(input,RequestOptions.defaults());}
}
