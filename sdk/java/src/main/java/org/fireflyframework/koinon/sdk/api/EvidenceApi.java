// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class EvidenceApi {
private final Transport transport; private final String prefix;
public EvidenceApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public EvidenceManifest conversation(MessageSelection input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/evidence/conversations",input,options,transport.type(EvidenceManifest.class));}
public EvidenceManifest conversation(MessageSelection input){return conversation(input,RequestOptions.defaults());}
public CompletableFuture<EvidenceManifest> conversationAsync(MessageSelection input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/evidence/conversations",input,options,transport.type(EvidenceManifest.class));}
public CompletableFuture<EvidenceManifest> conversationAsync(MessageSelection input){return conversationAsync(input,RequestOptions.defaults());}
}
