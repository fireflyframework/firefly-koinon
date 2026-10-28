// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityProviderPatch contract. */
public record IdentityProviderPatch(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("settings") JsonField<IdentityProviderSettings> settings,
    @JsonProperty("credential") JsonField<IdentityProviderCredential> credential,
    @JsonProperty("credential_reference") JsonField<String> credentialReference
) {

    public static IdentityProviderPatch empty(){return new IdentityProviderPatch(null,null,null,null,null);}
    public IdentityProviderPatch withExpectedRevision(Long value){return new IdentityProviderPatch(value,name,settings,credential,credentialReference);}
    public IdentityProviderPatch withName(String value){return new IdentityProviderPatch(expectedRevision,JsonField.of(value),settings,credential,credentialReference);}
    public IdentityProviderPatch clearName(){return new IdentityProviderPatch(expectedRevision,JsonField.clear(),settings,credential,credentialReference);}
    public IdentityProviderPatch omitName(){return new IdentityProviderPatch(expectedRevision,null,settings,credential,credentialReference);}
    public IdentityProviderPatch withSettings(IdentityProviderSettings value){return new IdentityProviderPatch(expectedRevision,name,JsonField.of(value),credential,credentialReference);}
    public IdentityProviderPatch clearSettings(){return new IdentityProviderPatch(expectedRevision,name,JsonField.clear(),credential,credentialReference);}
    public IdentityProviderPatch omitSettings(){return new IdentityProviderPatch(expectedRevision,name,null,credential,credentialReference);}
    public IdentityProviderPatch withCredential(IdentityProviderCredential value){return new IdentityProviderPatch(expectedRevision,name,settings,JsonField.of(value),credentialReference);}
    public IdentityProviderPatch clearCredential(){return new IdentityProviderPatch(expectedRevision,name,settings,JsonField.clear(),credentialReference);}
    public IdentityProviderPatch omitCredential(){return new IdentityProviderPatch(expectedRevision,name,settings,null,credentialReference);}
    public IdentityProviderPatch withCredentialReference(String value){return new IdentityProviderPatch(expectedRevision,name,settings,credential,JsonField.of(value));}
    public IdentityProviderPatch clearCredentialReference(){return new IdentityProviderPatch(expectedRevision,name,settings,credential,JsonField.clear());}
    public IdentityProviderPatch omitCredentialReference(){return new IdentityProviderPatch(expectedRevision,name,settings,credential,null);}
}
