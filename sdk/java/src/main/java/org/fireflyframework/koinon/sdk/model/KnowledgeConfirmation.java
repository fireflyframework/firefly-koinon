// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeConfirmation contract. */
public record KnowledgeConfirmation(
    @JsonProperty("confirm") Boolean confirm,
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("authorization_digest") String authorizationDigest
) {

    public static KnowledgeConfirmation empty(){return new KnowledgeConfirmation(null,null,null);}
    public KnowledgeConfirmation withConfirm(Boolean value){return new KnowledgeConfirmation(value,expectedRevision,authorizationDigest);}
    public KnowledgeConfirmation withExpectedRevision(Long value){return new KnowledgeConfirmation(confirm,value,authorizationDigest);}
    public KnowledgeConfirmation withAuthorizationDigest(String value){return new KnowledgeConfirmation(confirm,expectedRevision,value);}
}
