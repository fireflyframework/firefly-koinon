// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical EntraCredential contract. */
public record EntraCredential(
    @JsonProperty("kind") EntraCredentialKind kind,
    @JsonProperty("secret") String secret,
    @JsonProperty("directory_secret") JsonField<String> directorySecret
) implements IdentityProviderCredential {

    public static EntraCredential empty(){return new EntraCredential(null,null,null);}
    public EntraCredential withKind(EntraCredentialKind value){return new EntraCredential(value,secret,directorySecret);}
    public EntraCredential withSecret(String value){return new EntraCredential(kind,value,directorySecret);}
    public EntraCredential withDirectorySecret(String value){return new EntraCredential(kind,secret,JsonField.of(value));}
    public EntraCredential clearDirectorySecret(){return new EntraCredential(kind,secret,JsonField.clear());}
    public EntraCredential omitDirectorySecret(){return new EntraCredential(kind,secret,null);}
    @Override public String toString(){return "EntraCredential[credentials=<redacted>]";}
}
