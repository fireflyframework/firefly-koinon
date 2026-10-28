// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KeycloakSettings contract. */
public record KeycloakSettings(
    @JsonProperty("kind") KeycloakCredentialKind kind,
    @JsonProperty("issuer") String issuer,
    @JsonProperty("client_id") String clientId,
    @JsonProperty("directory_client_id") JsonField<String> directoryClientId,
    @JsonProperty("membership_mode") EntraSettingsMembershipMode membershipMode
) implements IdentityProviderSettings {

    public static KeycloakSettings empty(){return new KeycloakSettings(null,null,null,null,null);}
    public KeycloakSettings withKind(KeycloakCredentialKind value){return new KeycloakSettings(value,issuer,clientId,directoryClientId,membershipMode);}
    public KeycloakSettings withIssuer(String value){return new KeycloakSettings(kind,value,clientId,directoryClientId,membershipMode);}
    public KeycloakSettings withClientId(String value){return new KeycloakSettings(kind,issuer,value,directoryClientId,membershipMode);}
    public KeycloakSettings withDirectoryClientId(String value){return new KeycloakSettings(kind,issuer,clientId,JsonField.of(value),membershipMode);}
    public KeycloakSettings clearDirectoryClientId(){return new KeycloakSettings(kind,issuer,clientId,JsonField.clear(),membershipMode);}
    public KeycloakSettings omitDirectoryClientId(){return new KeycloakSettings(kind,issuer,clientId,null,membershipMode);}
    public KeycloakSettings withMembershipMode(EntraSettingsMembershipMode value){return new KeycloakSettings(kind,issuer,clientId,directoryClientId,value);}
}
