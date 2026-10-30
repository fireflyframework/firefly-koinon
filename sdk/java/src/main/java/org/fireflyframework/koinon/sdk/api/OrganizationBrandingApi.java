// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class OrganizationBrandingApi {
private final Transport transport; private final String prefix;
public OrganizationBrandingApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public OrganizationBranding get(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/branding",null,options,transport.type(OrganizationBranding.class));}
public OrganizationBranding get(){return get(RequestOptions.defaults());}
public CompletableFuture<OrganizationBranding> getAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/branding",null,options,transport.type(OrganizationBranding.class));}
public CompletableFuture<OrganizationBranding> getAsync(){return getAsync(RequestOptions.defaults());}
public OrganizationBranding update(OrganizationBrandingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/branding",input,options,transport.type(OrganizationBranding.class));}
public OrganizationBranding update(OrganizationBrandingInput input){return update(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationBranding> updateAsync(OrganizationBrandingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/branding",input,options,transport.type(OrganizationBranding.class));}
public CompletableFuture<OrganizationBranding> updateAsync(OrganizationBrandingInput input){return updateAsync(input,RequestOptions.defaults());}
public OrganizationBranding reset(BrandingResetInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/branding/reset",input,options,transport.type(OrganizationBranding.class));}
public OrganizationBranding reset(BrandingResetInput input){return reset(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationBranding> resetAsync(BrandingResetInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/branding/reset",input,options,transport.type(OrganizationBranding.class));}
public CompletableFuture<OrganizationBranding> resetAsync(BrandingResetInput input){return resetAsync(input,RequestOptions.defaults());}
}
