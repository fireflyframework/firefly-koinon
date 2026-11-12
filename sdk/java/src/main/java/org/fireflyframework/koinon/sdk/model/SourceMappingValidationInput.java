// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceMappingValidationInput contract. */
public record SourceMappingValidationInput(
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
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("mapping_id") JsonField<String> mappingId,
    @JsonProperty("expected_revision") JsonField<Long> expectedRevision
) {
    public SourceMappingValidationInput {
        excludedIds=excludedIds==null?null:List.copyOf(excludedIds);
        formats=formats==null?null:List.copyOf(formats);
        replacementResolutions=replacementResolutions==null?null:List.copyOf(replacementResolutions);
    }

    public static SourceMappingValidationInput empty(){return new SourceMappingValidationInput(null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null);}
    public SourceMappingValidationInput withConnectionId(String value){return new SourceMappingValidationInput(value,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withDriveId(String value){return new SourceMappingValidationInput(connectionId,value,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withRootId(String value){return new SourceMappingValidationInput(connectionId,driveId,value,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withDestination(BulkDestination value){return new SourceMappingValidationInput(connectionId,driveId,rootId,value,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withRecursive(Boolean value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,value,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withRemovalPolicy(MappingReviewInputRemovalPolicy value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,value,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withSchemaVersion(Long value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,value,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withMode(AddKnowledgeMode value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,value,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withHierarchy(MappingReviewInputHierarchy value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,value,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withExcludedIds(List<String> value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,value,formats,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withFormats(List<String> value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,value,schedule,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withSchedule(SourceSchedule value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,value,replacementResolutions,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withReplacementResolutions(List<ReplacementResolutionInput> value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,value,operationId,mappingId,expectedRevision);}
    public SourceMappingValidationInput withOperationId(String value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,value,mappingId,expectedRevision);}
    public SourceMappingValidationInput withMappingId(String value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,JsonField.of(value),expectedRevision);}
    public SourceMappingValidationInput clearMappingId(){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,JsonField.clear(),expectedRevision);}
    public SourceMappingValidationInput omitMappingId(){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,null,expectedRevision);}
    public SourceMappingValidationInput withExpectedRevision(Long value){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,JsonField.of(value));}
    public SourceMappingValidationInput clearExpectedRevision(){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,JsonField.clear());}
    public SourceMappingValidationInput omitExpectedRevision(){return new SourceMappingValidationInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions,operationId,mappingId,null);}
}
