// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationKnowledgeSettings contract. */
public record OrganizationKnowledgeSettings(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("schema_version") Long schemaVersion,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("origin") KnowledgeSettingsOrigin origin,
    @JsonProperty("documents") DocumentKnowledgeSettings documents,
    @JsonProperty("structured") StructuredKnowledgeSettings structured,
    @JsonProperty("capabilities") OrganizationKnowledgeCapabilities capabilities
) {

    public static OrganizationKnowledgeSettings empty(){return new OrganizationKnowledgeSettings(null,null,null,null,null,null,null);}
    public OrganizationKnowledgeSettings withTenantId(String value){return new OrganizationKnowledgeSettings(value,schemaVersion,revision,origin,documents,structured,capabilities);}
    public OrganizationKnowledgeSettings withSchemaVersion(Long value){return new OrganizationKnowledgeSettings(tenantId,value,revision,origin,documents,structured,capabilities);}
    public OrganizationKnowledgeSettings withRevision(Integer value){return new OrganizationKnowledgeSettings(tenantId,schemaVersion,value,origin,documents,structured,capabilities);}
    public OrganizationKnowledgeSettings withOrigin(KnowledgeSettingsOrigin value){return new OrganizationKnowledgeSettings(tenantId,schemaVersion,revision,value,documents,structured,capabilities);}
    public OrganizationKnowledgeSettings withDocuments(DocumentKnowledgeSettings value){return new OrganizationKnowledgeSettings(tenantId,schemaVersion,revision,origin,value,structured,capabilities);}
    public OrganizationKnowledgeSettings withStructured(StructuredKnowledgeSettings value){return new OrganizationKnowledgeSettings(tenantId,schemaVersion,revision,origin,documents,value,capabilities);}
    public OrganizationKnowledgeSettings withCapabilities(OrganizationKnowledgeCapabilities value){return new OrganizationKnowledgeSettings(tenantId,schemaVersion,revision,origin,documents,structured,value);}
}
