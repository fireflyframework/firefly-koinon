// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class IdentityApi {
private final Transport transport; private final String prefix;
public IdentityApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public IdentityProviderPage list(IdentityFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/identity/providers",null,options,transport.type(IdentityProviderPage.class));}
public IdentityProviderPage list(IdentityFilter filter){return list(filter,RequestOptions.defaults());}
public IdentityProviderPage list(){return list(IdentityFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<IdentityProviderPage> listAsync(IdentityFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/identity/providers",null,options,transport.type(IdentityProviderPage.class));}
public CompletableFuture<IdentityProviderPage> listAsync(IdentityFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<IdentityProviderPage> listAsync(){return listAsync(IdentityFilter.empty(),RequestOptions.defaults());}
public IdentityProvider create(IdentityProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/identity/providers",input,options,transport.type(IdentityProvider.class));}
public IdentityProvider create(IdentityProviderInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<IdentityProvider> createAsync(IdentityProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/identity/providers",input,options,transport.type(IdentityProvider.class));}
public CompletableFuture<IdentityProvider> createAsync(IdentityProviderInput input){return createAsync(input,RequestOptions.defaults());}
public IdentityProvider get(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/identity/providers/"+Transport.id(providerId),null,options,transport.type(IdentityProvider.class));}
public IdentityProvider get(String providerId){return get(providerId,RequestOptions.defaults());}
public CompletableFuture<IdentityProvider> getAsync(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/identity/providers/"+Transport.id(providerId),null,options,transport.type(IdentityProvider.class));}
public CompletableFuture<IdentityProvider> getAsync(String providerId){return getAsync(providerId,RequestOptions.defaults());}
public IdentityProvider update(String providerId,IdentityProviderPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/identity/providers/"+Transport.id(providerId),input,options,transport.type(IdentityProvider.class));}
public IdentityProvider update(String providerId,IdentityProviderPatch input){return update(providerId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityProvider> updateAsync(String providerId,IdentityProviderPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/identity/providers/"+Transport.id(providerId),input,options,transport.type(IdentityProvider.class));}
public CompletableFuture<IdentityProvider> updateAsync(String providerId,IdentityProviderPatch input){return updateAsync(providerId,input,RequestOptions.defaults());}
public IdentityValidation test(String providerId,IdentityRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/test",input,options,transport.type(IdentityValidation.class));}
public IdentityValidation test(String providerId,IdentityRevision input){return test(providerId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityValidation> testAsync(String providerId,IdentityRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/test",input,options,transport.type(IdentityValidation.class));}
public CompletableFuture<IdentityValidation> testAsync(String providerId,IdentityRevision input){return testAsync(providerId,input,RequestOptions.defaults());}
public IdentityValidation testStatus(String providerId,String validationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/tests/"+Transport.id(validationId),null,options,transport.type(IdentityValidation.class));}
public IdentityValidation testStatus(String providerId,String validationId){return testStatus(providerId,validationId,RequestOptions.defaults());}
public CompletableFuture<IdentityValidation> testStatusAsync(String providerId,String validationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/tests/"+Transport.id(validationId),null,options,transport.type(IdentityValidation.class));}
public CompletableFuture<IdentityValidation> testStatusAsync(String providerId,String validationId){return testStatusAsync(providerId,validationId,RequestOptions.defaults());}
public IdentityGroupPage groups(String providerId,IdentityGroupFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/groups",null,options,transport.type(IdentityGroupPage.class));}
public IdentityGroupPage groups(String providerId,IdentityGroupFilter filter){return groups(providerId,filter,RequestOptions.defaults());}
public IdentityGroupPage groups(String providerId){return groups(providerId,IdentityGroupFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<IdentityGroupPage> groupsAsync(String providerId,IdentityGroupFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/groups",null,options,transport.type(IdentityGroupPage.class));}
public CompletableFuture<IdentityGroupPage> groupsAsync(String providerId,IdentityGroupFilter filter){return groupsAsync(providerId,filter,RequestOptions.defaults());}
public CompletableFuture<IdentityGroupPage> groupsAsync(String providerId){return groupsAsync(providerId,IdentityGroupFilter.empty(),RequestOptions.defaults());}
public IdentityMappingPage mappings(String providerId,IdentityMappingFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings",null,options,transport.type(IdentityMappingPage.class));}
public IdentityMappingPage mappings(String providerId,IdentityMappingFilter filter){return mappings(providerId,filter,RequestOptions.defaults());}
public IdentityMappingPage mappings(String providerId){return mappings(providerId,IdentityMappingFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<IdentityMappingPage> mappingsAsync(String providerId,IdentityMappingFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings",null,options,transport.type(IdentityMappingPage.class));}
public CompletableFuture<IdentityMappingPage> mappingsAsync(String providerId,IdentityMappingFilter filter){return mappingsAsync(providerId,filter,RequestOptions.defaults());}
public CompletableFuture<IdentityMappingPage> mappingsAsync(String providerId){return mappingsAsync(providerId,IdentityMappingFilter.empty(),RequestOptions.defaults());}
public IdentityMapping createMapping(String providerId,IdentityMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings",input,options,transport.type(IdentityMapping.class));}
public IdentityMapping createMapping(String providerId,IdentityMappingInput input){return createMapping(providerId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityMapping> createMappingAsync(String providerId,IdentityMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings",input,options,transport.type(IdentityMapping.class));}
public CompletableFuture<IdentityMapping> createMappingAsync(String providerId,IdentityMappingInput input){return createMappingAsync(providerId,input,RequestOptions.defaults());}
public IdentityMapping updateMapping(String providerId,String mappingId,IdentityMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings/"+Transport.id(mappingId),input,options,transport.type(IdentityMapping.class));}
public IdentityMapping updateMapping(String providerId,String mappingId,IdentityMappingInput input){return updateMapping(providerId,mappingId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityMapping> updateMappingAsync(String providerId,String mappingId,IdentityMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings/"+Transport.id(mappingId),input,options,transport.type(IdentityMapping.class));}
public CompletableFuture<IdentityMapping> updateMappingAsync(String providerId,String mappingId,IdentityMappingInput input){return updateMappingAsync(providerId,mappingId,input,RequestOptions.defaults());}
public Void removeMapping(String providerId,String mappingId,IdentityMappingDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("DELETE",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings/"+Transport.id(mappingId),null,options,transport.type(Void.class));}
public Void removeMapping(String providerId,String mappingId,IdentityMappingDeleteFilter filter){return removeMapping(providerId,mappingId,filter,RequestOptions.defaults());}
public CompletableFuture<Void> removeMappingAsync(String providerId,String mappingId,IdentityMappingDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("DELETE",prefix+"/identity/providers/"+Transport.id(providerId)+"/mappings/"+Transport.id(mappingId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> removeMappingAsync(String providerId,String mappingId,IdentityMappingDeleteFilter filter){return removeMappingAsync(providerId,mappingId,filter,RequestOptions.defaults());}
public IdentityProvider activate(String providerId,IdentityActivation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/activate",input,options,transport.type(IdentityProvider.class));}
public IdentityProvider activate(String providerId,IdentityActivation input){return activate(providerId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityProvider> activateAsync(String providerId,IdentityActivation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/activate",input,options,transport.type(IdentityProvider.class));}
public CompletableFuture<IdentityProvider> activateAsync(String providerId,IdentityActivation input){return activateAsync(providerId,input,RequestOptions.defaults());}
public IdentityProvider disable(String providerId,IdentityRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/disable",input,options,transport.type(IdentityProvider.class));}
public IdentityProvider disable(String providerId,IdentityRevision input){return disable(providerId,input,RequestOptions.defaults());}
public CompletableFuture<IdentityProvider> disableAsync(String providerId,IdentityRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/identity/providers/"+Transport.id(providerId)+"/disable",input,options,transport.type(IdentityProvider.class));}
public CompletableFuture<IdentityProvider> disableAsync(String providerId,IdentityRevision input){return disableAsync(providerId,input,RequestOptions.defaults());}
}
