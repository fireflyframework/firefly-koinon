// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical TenantContext contract. */
public record TenantContext(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("roles") List<String> roles,
    @JsonProperty("permissions") List<String> permissions
) {
    public TenantContext {
        roles=roles==null?null:List.copyOf(roles);
        permissions=permissions==null?null:List.copyOf(permissions);
    }

}
