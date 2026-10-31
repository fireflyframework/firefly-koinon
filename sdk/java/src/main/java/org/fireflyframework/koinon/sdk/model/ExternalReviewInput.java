// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ExternalReviewInput contract. */
public record ExternalReviewInput(
    @JsonProperty("action") ExternalReviewInputAction action,
    @JsonProperty("destination_id") String destinationId,
    @JsonProperty("target_item_id") JsonField<String> targetItemId,
    @JsonProperty("expected_version") JsonField<Long> expectedVersion,
    @JsonProperty("content") KnowledgeContent content,
    @JsonProperty("source_receipt_ids") List<String> sourceReceiptIds
) {
    public ExternalReviewInput {
        sourceReceiptIds=sourceReceiptIds==null?null:List.copyOf(sourceReceiptIds);
    }

    public static ExternalReviewInput empty(){return new ExternalReviewInput(null,null,null,null,null,null);}
    public ExternalReviewInput withAction(ExternalReviewInputAction value){return new ExternalReviewInput(value,destinationId,targetItemId,expectedVersion,content,sourceReceiptIds);}
    public ExternalReviewInput withDestinationId(String value){return new ExternalReviewInput(action,value,targetItemId,expectedVersion,content,sourceReceiptIds);}
    public ExternalReviewInput withTargetItemId(String value){return new ExternalReviewInput(action,destinationId,JsonField.of(value),expectedVersion,content,sourceReceiptIds);}
    public ExternalReviewInput clearTargetItemId(){return new ExternalReviewInput(action,destinationId,JsonField.clear(),expectedVersion,content,sourceReceiptIds);}
    public ExternalReviewInput omitTargetItemId(){return new ExternalReviewInput(action,destinationId,null,expectedVersion,content,sourceReceiptIds);}
    public ExternalReviewInput withExpectedVersion(Long value){return new ExternalReviewInput(action,destinationId,targetItemId,JsonField.of(value),content,sourceReceiptIds);}
    public ExternalReviewInput clearExpectedVersion(){return new ExternalReviewInput(action,destinationId,targetItemId,JsonField.clear(),content,sourceReceiptIds);}
    public ExternalReviewInput omitExpectedVersion(){return new ExternalReviewInput(action,destinationId,targetItemId,null,content,sourceReceiptIds);}
    public ExternalReviewInput withContent(KnowledgeContent value){return new ExternalReviewInput(action,destinationId,targetItemId,expectedVersion,value,sourceReceiptIds);}
    public ExternalReviewInput withSourceReceiptIds(List<String> value){return new ExternalReviewInput(action,destinationId,targetItemId,expectedVersion,content,value);}
}
