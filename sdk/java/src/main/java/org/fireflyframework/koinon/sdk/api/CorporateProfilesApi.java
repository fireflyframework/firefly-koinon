// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class CorporateProfilesApi {
private final Transport transport; private final String prefix;
public CorporateProfilesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public OrganizationPresentation presentation(OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/people/me/presentation",null,options,transport.type(OrganizationPresentation.class));}
public OrganizationPresentation presentation(OrganizationScopeFilter filter){return presentation(filter,RequestOptions.defaults());}
public OrganizationPresentation presentation(){return presentation(OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPresentation> presentationAsync(OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/people/me/presentation",null,options,transport.type(OrganizationPresentation.class));}
public CompletableFuture<OrganizationPresentation> presentationAsync(OrganizationScopeFilter filter){return presentationAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPresentation> presentationAsync(){return presentationAsync(OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public OrganizationPresentation updatePresentation(OrganizationPresentationInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/organization/people/me/presentation",input,options,transport.type(OrganizationPresentation.class));}
public OrganizationPresentation updatePresentation(OrganizationPresentationInput input,OrganizationScopeFilter filter){return updatePresentation(input,filter,RequestOptions.defaults());}
public OrganizationPresentation updatePresentation(OrganizationPresentationInput input){return updatePresentation(input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPresentation> updatePresentationAsync(OrganizationPresentationInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/organization/people/me/presentation",input,options,transport.type(OrganizationPresentation.class));}
public CompletableFuture<OrganizationPresentation> updatePresentationAsync(OrganizationPresentationInput input,OrganizationScopeFilter filter){return updatePresentationAsync(input,filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPresentation> updatePresentationAsync(OrganizationPresentationInput input){return updatePresentationAsync(input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CorporateProfileRefresh refreshSelf(CorporateProfileRefreshInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/organization/people/me/profile-refresh",input,options,transport.type(CorporateProfileRefresh.class));}
public CorporateProfileRefresh refreshSelf(CorporateProfileRefreshInput input,OrganizationScopeFilter filter){return refreshSelf(input,filter,RequestOptions.defaults());}
public CorporateProfileRefresh refreshSelf(CorporateProfileRefreshInput input){return refreshSelf(input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<CorporateProfileRefresh> refreshSelfAsync(CorporateProfileRefreshInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/organization/people/me/profile-refresh",input,options,transport.type(CorporateProfileRefresh.class));}
public CompletableFuture<CorporateProfileRefresh> refreshSelfAsync(CorporateProfileRefreshInput input,OrganizationScopeFilter filter){return refreshSelfAsync(input,filter,RequestOptions.defaults());}
public CompletableFuture<CorporateProfileRefresh> refreshSelfAsync(CorporateProfileRefreshInput input){return refreshSelfAsync(input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CorporateProfileRefresh refreshPerson(String personId,CorporateProfileRefreshInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/organization/people/"+Transport.id(personId)+"/profile-refresh",input,options,transport.type(CorporateProfileRefresh.class));}
public CorporateProfileRefresh refreshPerson(String personId,CorporateProfileRefreshInput input,OrganizationScopeFilter filter){return refreshPerson(personId,input,filter,RequestOptions.defaults());}
public CorporateProfileRefresh refreshPerson(String personId,CorporateProfileRefreshInput input){return refreshPerson(personId,input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<CorporateProfileRefresh> refreshPersonAsync(String personId,CorporateProfileRefreshInput input,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/organization/people/"+Transport.id(personId)+"/profile-refresh",input,options,transport.type(CorporateProfileRefresh.class));}
public CompletableFuture<CorporateProfileRefresh> refreshPersonAsync(String personId,CorporateProfileRefreshInput input,OrganizationScopeFilter filter){return refreshPersonAsync(personId,input,filter,RequestOptions.defaults());}
public CompletableFuture<CorporateProfileRefresh> refreshPersonAsync(String personId,CorporateProfileRefreshInput input){return refreshPersonAsync(personId,input,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
}
