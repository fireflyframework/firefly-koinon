// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical GoogleWorkspaceSettings contract. */
public record GoogleWorkspaceSettings(
    @JsonProperty("kind") GoogleCredentialKind kind,
    @JsonProperty("client_id") String clientId,
    @JsonProperty("hosted_domains") List<String> hostedDomains,
    @JsonProperty("customer_id") JsonField<String> customerId,
    @JsonProperty("membership_mode") EntraSettingsMembershipMode membershipMode
) implements IdentityProviderSettings {
    public GoogleWorkspaceSettings {
        hostedDomains=hostedDomains==null?null:List.copyOf(hostedDomains);
    }

    public static GoogleWorkspaceSettings empty(){return new GoogleWorkspaceSettings(null,null,null,null,null);}
    public GoogleWorkspaceSettings withKind(GoogleCredentialKind value){return new GoogleWorkspaceSettings(value,clientId,hostedDomains,customerId,membershipMode);}
    public GoogleWorkspaceSettings withClientId(String value){return new GoogleWorkspaceSettings(kind,value,hostedDomains,customerId,membershipMode);}
    public GoogleWorkspaceSettings withHostedDomains(List<String> value){return new GoogleWorkspaceSettings(kind,clientId,value,customerId,membershipMode);}
    public GoogleWorkspaceSettings withCustomerId(String value){return new GoogleWorkspaceSettings(kind,clientId,hostedDomains,JsonField.of(value),membershipMode);}
    public GoogleWorkspaceSettings clearCustomerId(){return new GoogleWorkspaceSettings(kind,clientId,hostedDomains,JsonField.clear(),membershipMode);}
    public GoogleWorkspaceSettings omitCustomerId(){return new GoogleWorkspaceSettings(kind,clientId,hostedDomains,null,membershipMode);}
    public GoogleWorkspaceSettings withMembershipMode(EntraSettingsMembershipMode value){return new GoogleWorkspaceSettings(kind,clientId,hostedDomains,customerId,value);}
}
