// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical MemberUpdate contract. */
public record MemberUpdate(
    @JsonProperty("role") JsonField<MembershipRole> role,
    @JsonProperty("active") JsonField<Boolean> active
) {

    public static MemberUpdate empty(){return new MemberUpdate(null,null);}
    public MemberUpdate withRole(MembershipRole value){return new MemberUpdate(JsonField.of(value),active);}
    public MemberUpdate clearRole(){return new MemberUpdate(JsonField.clear(),active);}
    public MemberUpdate omitRole(){return new MemberUpdate(null,active);}
    public MemberUpdate withActive(Boolean value){return new MemberUpdate(role,JsonField.of(value));}
    public MemberUpdate clearActive(){return new MemberUpdate(role,JsonField.clear());}
    public MemberUpdate omitActive(){return new MemberUpdate(role,null);}
}
