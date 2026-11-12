// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceExistingPolicyReviewInput contract. */
public record SourceExistingPolicyReviewInput(
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("connection_id") String connectionId,
    @JsonProperty("drive_id") String driveId,
    @JsonProperty("root_id") String rootId,
    @JsonProperty("destination") BulkDestination destination,
    @JsonProperty("recursive") Boolean recursive,
    @JsonProperty("removal_policy") MappingReviewInputRemovalPolicy removalPolicy,
    @JsonProperty("schema_version") Long schemaVersion,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("hierarchy") MappingReviewInputHierarchy hierarchy,
    @JsonProperty("excluded_ids") List<String> excludedIds,
    @JsonProperty("formats") List<String> formats,
    @JsonProperty("schedule") SourceSchedule schedule,
    @JsonProperty("replacement_resolutions") List<ReplacementResolutionInput> replacementResolutions,
    @JsonProperty("validation_id") JsonField<String> validationId,
    @JsonProperty("expected_revision") Integer expectedRevision
) {
    public SourceExistingPolicyReviewInput {
        excludedIds=excludedIds==null?null:List.copyOf(excludedIds);
        formats=formats==null?null:List.copyOf(formats);
        replacementResolutions=replacementResolutions==null?null:List.copyOf(replacementResolutions);
    }

    public static SourceExistingPolicyReviewInput empty(){return new SourceExistingPolicyReviewInput(null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null);}
    public SourceExistingPolicyReviewInput withOperationId(String value){return new SourceExistingPolicyReviewInput(value,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withConnectionId(String value){return new SourceExistingPolicyReviewInput(operationId,value,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withDriveId(String value){return new SourceExistingPolicyReviewInput(operationId,connectionId,value,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withRootId(String value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,value,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withDestination(BulkDestination value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,value,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withRecursive(Boolean value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,value,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withRemovalPolicy(MappingReviewInputRemovalPolicy value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,value,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withSchemaVersion(Long value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,value,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withMode(AddKnowledgeMode value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,value,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withHierarchy(MappingReviewInputHierarchy value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,value,excludedIds,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withExcludedIds(List<String> value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,value,formats,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withFormats(List<String> value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,value,schedule,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withSchedule(SourceSchedule value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,value,replacementResolutions,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withReplacementResolutions(List<ReplacementResolutionInput> value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,value,validationId,expectedRevision);}
    public SourceExistingPolicyReviewInput withValidationId(String value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,JsonField.of(value),expectedRevision);}
    public SourceExistingPolicyReviewInput clearValidationId(){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,JsonField.clear(),expectedRevision);}
    public SourceExistingPolicyReviewInput omitValidationId(){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,null,expectedRevision);}
    public SourceExistingPolicyReviewInput withExpectedRevision(Integer value){return new SourceExistingPolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId,value);}
}
