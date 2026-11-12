// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourcePolicyReviewInput contract. */
public record SourcePolicyReviewInput(
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
    @JsonProperty("validation_id") JsonField<String> validationId
) {
    public SourcePolicyReviewInput {
        excludedIds=excludedIds==null?null:List.copyOf(excludedIds);
        formats=formats==null?null:List.copyOf(formats);
        replacementResolutions=replacementResolutions==null?null:List.copyOf(replacementResolutions);
    }

    public static SourcePolicyReviewInput empty(){return new SourcePolicyReviewInput(null,null,null,null,null,null,null,null,null,null,null,null,null,null,null);}
    public SourcePolicyReviewInput withOperationId(String value){return new SourcePolicyReviewInput(value,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withConnectionId(String value){return new SourcePolicyReviewInput(operationId,value,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withDriveId(String value){return new SourcePolicyReviewInput(operationId,connectionId,value,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withRootId(String value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,value,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withDestination(BulkDestination value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,value,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withRecursive(Boolean value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,value,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withRemovalPolicy(MappingReviewInputRemovalPolicy value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,value,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withSchemaVersion(Long value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,value,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withMode(AddKnowledgeMode value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,value,hierarchy,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withHierarchy(MappingReviewInputHierarchy value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,value,excludedIds,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withExcludedIds(List<String> value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,value,formats,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withFormats(List<String> value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,value,schedule,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withSchedule(SourceSchedule value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,value,replacementResolutions,validationId);}
    public SourcePolicyReviewInput withReplacementResolutions(List<ReplacementResolutionInput> value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,value,validationId);}
    public SourcePolicyReviewInput withValidationId(String value){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,JsonField.of(value));}
    public SourcePolicyReviewInput clearValidationId(){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,JsonField.clear());}
    public SourcePolicyReviewInput omitValidationId(){return new SourcePolicyReviewInput(operationId,connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,null);}
}
