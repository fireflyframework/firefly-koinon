// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityProviderInput contract. */
public record IdentityProviderInput(
    @JsonProperty("kind") IdentityProviderKind kind,
    @JsonProperty("name") String name,
    @JsonProperty("broker_alias") JsonField<String> brokerAlias,
    @JsonProperty("settings") IdentityProviderSettings settings,
    @JsonProperty("credential") JsonField<IdentityProviderCredential> credential,
    @JsonProperty("credential_reference") JsonField<String> credentialReference
) {

    public static IdentityProviderInput empty(){return new IdentityProviderInput(null,null,null,null,null,null);}
    public IdentityProviderInput withKind(IdentityProviderKind value){return new IdentityProviderInput(value,name,brokerAlias,settings,credential,credentialReference);}
    public IdentityProviderInput withName(String value){return new IdentityProviderInput(kind,value,brokerAlias,settings,credential,credentialReference);}
    public IdentityProviderInput withBrokerAlias(String value){return new IdentityProviderInput(kind,name,JsonField.of(value),settings,credential,credentialReference);}
    public IdentityProviderInput clearBrokerAlias(){return new IdentityProviderInput(kind,name,JsonField.clear(),settings,credential,credentialReference);}
    public IdentityProviderInput omitBrokerAlias(){return new IdentityProviderInput(kind,name,null,settings,credential,credentialReference);}
    public IdentityProviderInput withSettings(IdentityProviderSettings value){return new IdentityProviderInput(kind,name,brokerAlias,value,credential,credentialReference);}
    public IdentityProviderInput withCredential(IdentityProviderCredential value){return new IdentityProviderInput(kind,name,brokerAlias,settings,JsonField.of(value),credentialReference);}
    public IdentityProviderInput clearCredential(){return new IdentityProviderInput(kind,name,brokerAlias,settings,JsonField.clear(),credentialReference);}
    public IdentityProviderInput omitCredential(){return new IdentityProviderInput(kind,name,brokerAlias,settings,null,credentialReference);}
    public IdentityProviderInput withCredentialReference(String value){return new IdentityProviderInput(kind,name,brokerAlias,settings,credential,JsonField.of(value));}
    public IdentityProviderInput clearCredentialReference(){return new IdentityProviderInput(kind,name,brokerAlias,settings,credential,JsonField.clear());}
    public IdentityProviderInput omitCredentialReference(){return new IdentityProviderInput(kind,name,brokerAlias,settings,credential,null);}
}
