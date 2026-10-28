// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeIntentInput contract. */
public record KnowledgeIntentInput(
    @JsonProperty("action") KnowledgeCommitReceiptAction action,
    @JsonProperty("destination_id") String destinationId,
    @JsonProperty("target_item_id") JsonField<String> targetItemId,
    @JsonProperty("expected_version") JsonField<Long> expectedVersion,
    @JsonProperty("content") KnowledgeContent content,
    @JsonProperty("origin") KnowledgeOrigin origin
) {

    public static KnowledgeIntentInput empty(){return new KnowledgeIntentInput(null,null,null,null,null,null);}
    public KnowledgeIntentInput withAction(KnowledgeCommitReceiptAction value){return new KnowledgeIntentInput(value,destinationId,targetItemId,expectedVersion,content,origin);}
    public KnowledgeIntentInput withDestinationId(String value){return new KnowledgeIntentInput(action,value,targetItemId,expectedVersion,content,origin);}
    public KnowledgeIntentInput withTargetItemId(String value){return new KnowledgeIntentInput(action,destinationId,JsonField.of(value),expectedVersion,content,origin);}
    public KnowledgeIntentInput clearTargetItemId(){return new KnowledgeIntentInput(action,destinationId,JsonField.clear(),expectedVersion,content,origin);}
    public KnowledgeIntentInput omitTargetItemId(){return new KnowledgeIntentInput(action,destinationId,null,expectedVersion,content,origin);}
    public KnowledgeIntentInput withExpectedVersion(Long value){return new KnowledgeIntentInput(action,destinationId,targetItemId,JsonField.of(value),content,origin);}
    public KnowledgeIntentInput clearExpectedVersion(){return new KnowledgeIntentInput(action,destinationId,targetItemId,JsonField.clear(),content,origin);}
    public KnowledgeIntentInput omitExpectedVersion(){return new KnowledgeIntentInput(action,destinationId,targetItemId,null,content,origin);}
    public KnowledgeIntentInput withContent(KnowledgeContent value){return new KnowledgeIntentInput(action,destinationId,targetItemId,expectedVersion,value,origin);}
    public KnowledgeIntentInput withOrigin(KnowledgeOrigin value){return new KnowledgeIntentInput(action,destinationId,targetItemId,expectedVersion,content,value);}
}
