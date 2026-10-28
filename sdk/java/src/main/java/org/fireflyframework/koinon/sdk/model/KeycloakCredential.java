// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KeycloakCredential contract. */
public record KeycloakCredential(
    @JsonProperty("kind") KeycloakCredentialKind kind,
    @JsonProperty("secret") String secret,
    @JsonProperty("directory_secret") JsonField<String> directorySecret
) implements IdentityProviderCredential {

    public static KeycloakCredential empty(){return new KeycloakCredential(null,null,null);}
    public KeycloakCredential withKind(KeycloakCredentialKind value){return new KeycloakCredential(value,secret,directorySecret);}
    public KeycloakCredential withSecret(String value){return new KeycloakCredential(kind,value,directorySecret);}
    public KeycloakCredential withDirectorySecret(String value){return new KeycloakCredential(kind,secret,JsonField.of(value));}
    public KeycloakCredential clearDirectorySecret(){return new KeycloakCredential(kind,secret,JsonField.clear());}
    public KeycloakCredential omitDirectorySecret(){return new KeycloakCredential(kind,secret,null);}
    @Override public String toString(){return "KeycloakCredential[credentials=<redacted>]";}
}
