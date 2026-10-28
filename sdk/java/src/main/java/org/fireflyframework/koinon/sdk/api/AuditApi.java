// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class AuditApi {
private final Transport transport; private final String prefix;
public AuditApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<AuditEvent> list(AuditFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/audit",null,options,transport.pageType(AuditEvent.class));}
public Page<AuditEvent> list(AuditFilter filter){return list(filter,RequestOptions.defaults());}
public Page<AuditEvent> list(){return list(AuditFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<AuditEvent>> listAsync(AuditFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/audit",null,options,transport.pageType(AuditEvent.class));}
public CompletableFuture<Page<AuditEvent>> listAsync(AuditFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<AuditEvent>> listAsync(){return listAsync(AuditFilter.empty(),RequestOptions.defaults());}
}
