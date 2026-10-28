// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class TokensApi {
private final Transport transport; private final String prefix;
public TokensApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public Page<PersonalToken> list(TokenFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/tokens",null,options,transport.pageType(PersonalToken.class));}
public Page<PersonalToken> list(TokenFilter filter){return list(filter,RequestOptions.defaults());}
public Page<PersonalToken> list(){return list(TokenFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<PersonalToken>> listAsync(TokenFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/tokens",null,options,transport.pageType(PersonalToken.class));}
public CompletableFuture<Page<PersonalToken>> listAsync(TokenFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<PersonalToken>> listAsync(){return listAsync(TokenFilter.empty(),RequestOptions.defaults());}
public TokenScopeOptions scopes(TokenScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/tokens/scopes",null,options,transport.type(TokenScopeOptions.class));}
public TokenScopeOptions scopes(TokenScopeFilter filter){return scopes(filter,RequestOptions.defaults());}
public CompletableFuture<TokenScopeOptions> scopesAsync(TokenScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/tokens/scopes",null,options,transport.type(TokenScopeOptions.class));}
public CompletableFuture<TokenScopeOptions> scopesAsync(TokenScopeFilter filter){return scopesAsync(filter,RequestOptions.defaults());}
public TokenCreated create(TokenInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/tokens",input,options,transport.type(TokenCreated.class));}
public TokenCreated create(TokenInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<TokenCreated> createAsync(TokenInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/tokens",input,options,transport.type(TokenCreated.class));}
public CompletableFuture<TokenCreated> createAsync(TokenInput input){return createAsync(input,RequestOptions.defaults());}
public Void revoke(String tokenId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/tokens/"+Transport.id(tokenId),null,options,transport.type(Void.class));}
public Void revoke(String tokenId){return revoke(tokenId,RequestOptions.defaults());}
public CompletableFuture<Void> revokeAsync(String tokenId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/tokens/"+Transport.id(tokenId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> revokeAsync(String tokenId){return revokeAsync(tokenId,RequestOptions.defaults());}
}
