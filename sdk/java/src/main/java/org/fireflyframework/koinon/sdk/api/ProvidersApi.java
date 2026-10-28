// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ProvidersApi {
private final Transport transport; private final String prefix;
public ProvidersApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ModelProvider create(ProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/providers",input,options,transport.type(ModelProvider.class));}
public ModelProvider create(ProviderInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<ModelProvider> createAsync(ProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/providers",input,options,transport.type(ModelProvider.class));}
public CompletableFuture<ModelProvider> createAsync(ProviderInput input){return createAsync(input,RequestOptions.defaults());}
public ModelProvider update(String providerId,ProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/providers/"+Transport.id(providerId),input,options,transport.type(ModelProvider.class));}
public ModelProvider update(String providerId,ProviderInput input){return update(providerId,input,RequestOptions.defaults());}
public CompletableFuture<ModelProvider> updateAsync(String providerId,ProviderInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/providers/"+Transport.id(providerId),input,options,transport.type(ModelProvider.class));}
public CompletableFuture<ModelProvider> updateAsync(String providerId,ProviderInput input){return updateAsync(providerId,input,RequestOptions.defaults());}
public ValidationResult validate(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/providers/"+Transport.id(providerId)+"/validate",null,options,transport.type(ValidationResult.class));}
public ValidationResult validate(String providerId){return validate(providerId,RequestOptions.defaults());}
public CompletableFuture<ValidationResult> validateAsync(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/providers/"+Transport.id(providerId)+"/validate",null,options,transport.type(ValidationResult.class));}
public CompletableFuture<ValidationResult> validateAsync(String providerId){return validateAsync(providerId,RequestOptions.defaults());}
}
