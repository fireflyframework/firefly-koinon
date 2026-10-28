// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ProviderInput contract. */
public record ProviderInput(
    @JsonProperty("api") JsonField<ModelApi> api,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("kind") JsonField<ProviderKind> kind,
    @JsonProperty("base_url") JsonField<String> baseUrl,
    @JsonProperty("model_ids") JsonField<List<String>> modelIds,
    @JsonProperty("secret") JsonField<String> secret,
    @JsonProperty("enabled") JsonField<Boolean> enabled
) {

    public static ProviderInput empty(){return new ProviderInput(null,null,null,null,null,null,null);}
    public ProviderInput withApi(ModelApi value){return new ProviderInput(JsonField.of(value),name,kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput clearApi(){return new ProviderInput(JsonField.clear(),name,kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput omitApi(){return new ProviderInput(null,name,kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput withName(String value){return new ProviderInput(api,JsonField.of(value),kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput clearName(){return new ProviderInput(api,JsonField.clear(),kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput omitName(){return new ProviderInput(api,null,kind,baseUrl,modelIds,secret,enabled);}
    public ProviderInput withKind(ProviderKind value){return new ProviderInput(api,name,JsonField.of(value),baseUrl,modelIds,secret,enabled);}
    public ProviderInput clearKind(){return new ProviderInput(api,name,JsonField.clear(),baseUrl,modelIds,secret,enabled);}
    public ProviderInput omitKind(){return new ProviderInput(api,name,null,baseUrl,modelIds,secret,enabled);}
    public ProviderInput withBaseUrl(String value){return new ProviderInput(api,name,kind,JsonField.of(value),modelIds,secret,enabled);}
    public ProviderInput clearBaseUrl(){return new ProviderInput(api,name,kind,JsonField.clear(),modelIds,secret,enabled);}
    public ProviderInput omitBaseUrl(){return new ProviderInput(api,name,kind,null,modelIds,secret,enabled);}
    public ProviderInput withModelIds(List<String> value){return new ProviderInput(api,name,kind,baseUrl,JsonField.of(value),secret,enabled);}
    public ProviderInput clearModelIds(){return new ProviderInput(api,name,kind,baseUrl,JsonField.clear(),secret,enabled);}
    public ProviderInput omitModelIds(){return new ProviderInput(api,name,kind,baseUrl,null,secret,enabled);}
    public ProviderInput withSecret(String value){return new ProviderInput(api,name,kind,baseUrl,modelIds,JsonField.of(value),enabled);}
    public ProviderInput clearSecret(){return new ProviderInput(api,name,kind,baseUrl,modelIds,JsonField.clear(),enabled);}
    public ProviderInput omitSecret(){return new ProviderInput(api,name,kind,baseUrl,modelIds,null,enabled);}
    public ProviderInput withEnabled(Boolean value){return new ProviderInput(api,name,kind,baseUrl,modelIds,secret,JsonField.of(value));}
    public ProviderInput clearEnabled(){return new ProviderInput(api,name,kind,baseUrl,modelIds,secret,JsonField.clear());}
    public ProviderInput omitEnabled(){return new ProviderInput(api,name,kind,baseUrl,modelIds,secret,null);}
}
