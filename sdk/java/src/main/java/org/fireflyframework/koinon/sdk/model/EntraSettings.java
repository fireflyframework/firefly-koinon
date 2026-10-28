// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical EntraSettings contract. */
public record EntraSettings(
    @JsonProperty("kind") EntraCredentialKind kind,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("client_id") String clientId,
    @JsonProperty("directory_client_id") JsonField<String> directoryClientId,
    @JsonProperty("membership_mode") EntraSettingsMembershipMode membershipMode
) implements IdentityProviderSettings {

    public static EntraSettings empty(){return new EntraSettings(null,null,null,null,null);}
    public EntraSettings withKind(EntraCredentialKind value){return new EntraSettings(value,tenantId,clientId,directoryClientId,membershipMode);}
    public EntraSettings withTenantId(String value){return new EntraSettings(kind,value,clientId,directoryClientId,membershipMode);}
    public EntraSettings withClientId(String value){return new EntraSettings(kind,tenantId,value,directoryClientId,membershipMode);}
    public EntraSettings withDirectoryClientId(String value){return new EntraSettings(kind,tenantId,clientId,JsonField.of(value),membershipMode);}
    public EntraSettings clearDirectoryClientId(){return new EntraSettings(kind,tenantId,clientId,JsonField.clear(),membershipMode);}
    public EntraSettings omitDirectoryClientId(){return new EntraSettings(kind,tenantId,clientId,null,membershipMode);}
    public EntraSettings withMembershipMode(EntraSettingsMembershipMode value){return new EntraSettings(kind,tenantId,clientId,directoryClientId,value);}
}
