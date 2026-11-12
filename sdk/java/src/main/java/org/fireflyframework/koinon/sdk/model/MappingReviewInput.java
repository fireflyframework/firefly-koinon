// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical MappingReviewInput contract. */
public record MappingReviewInput(
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
    @JsonProperty("replacement_resolutions") List<ReplacementResolutionInput> replacementResolutions
) {
    public MappingReviewInput {
        excludedIds=excludedIds==null?null:List.copyOf(excludedIds);
        formats=formats==null?null:List.copyOf(formats);
        replacementResolutions=replacementResolutions==null?null:List.copyOf(replacementResolutions);
    }

    public static MappingReviewInput empty(){return new MappingReviewInput(null,null,null,null,null,null,null,null,null,null,null,null,null);}
    public MappingReviewInput withConnectionId(String value){return new MappingReviewInput(value,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withDriveId(String value){return new MappingReviewInput(connectionId,value,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withRootId(String value){return new MappingReviewInput(connectionId,driveId,value,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withDestination(BulkDestination value){return new MappingReviewInput(connectionId,driveId,rootId,value,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withRecursive(Boolean value){return new MappingReviewInput(connectionId,driveId,rootId,destination,value,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withRemovalPolicy(MappingReviewInputRemovalPolicy value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,value,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withSchemaVersion(Long value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,value,mode,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withMode(AddKnowledgeMode value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,value,hierarchy,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withHierarchy(MappingReviewInputHierarchy value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,value,excludedIds,formats,schedule,replacementResolutions);}
    public MappingReviewInput withExcludedIds(List<String> value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,value,formats,schedule,replacementResolutions);}
    public MappingReviewInput withFormats(List<String> value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,value,schedule,replacementResolutions);}
    public MappingReviewInput withSchedule(SourceSchedule value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,value,replacementResolutions);}
    public MappingReviewInput withReplacementResolutions(List<ReplacementResolutionInput> value){return new MappingReviewInput(connectionId,driveId,rootId,destination,recursive,removalPolicy,schemaVersion,mode,hierarchy,excludedIds,formats,schedule,value);}
}
