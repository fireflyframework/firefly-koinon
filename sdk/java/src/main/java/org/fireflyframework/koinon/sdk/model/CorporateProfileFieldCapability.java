// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CorporateProfileFieldCapability contract. */
public record CorporateProfileFieldCapability(
    @JsonProperty("field") ProfileFieldName field,
    @JsonProperty("source") ProfileObservationSource source,
    @JsonProperty("supported") Boolean supported,
    @JsonProperty("required_permissions") List<String> requiredPermissions,
    @JsonProperty("code") String code
) {
    public CorporateProfileFieldCapability {
        requiredPermissions=requiredPermissions==null?null:List.copyOf(requiredPermissions);
    }

}
