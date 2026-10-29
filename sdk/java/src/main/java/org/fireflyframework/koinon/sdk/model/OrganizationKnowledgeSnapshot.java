// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationKnowledgeSnapshot contract. */
public record OrganizationKnowledgeSnapshot(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("schema_version") Long schemaVersion,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("origin") KnowledgeSettingsOrigin origin,
    @JsonProperty("documents") DocumentKnowledgeSettings documents,
    @JsonProperty("structured") StructuredKnowledgeSettings structured,
    @JsonProperty("digest") String digest
) {

    public static OrganizationKnowledgeSnapshot empty(){return new OrganizationKnowledgeSnapshot(null,null,null,null,null,null,null);}
    public OrganizationKnowledgeSnapshot withTenantId(String value){return new OrganizationKnowledgeSnapshot(value,schemaVersion,revision,origin,documents,structured,digest);}
    public OrganizationKnowledgeSnapshot withSchemaVersion(Long value){return new OrganizationKnowledgeSnapshot(tenantId,value,revision,origin,documents,structured,digest);}
    public OrganizationKnowledgeSnapshot withRevision(Integer value){return new OrganizationKnowledgeSnapshot(tenantId,schemaVersion,value,origin,documents,structured,digest);}
    public OrganizationKnowledgeSnapshot withOrigin(KnowledgeSettingsOrigin value){return new OrganizationKnowledgeSnapshot(tenantId,schemaVersion,revision,value,documents,structured,digest);}
    public OrganizationKnowledgeSnapshot withDocuments(DocumentKnowledgeSettings value){return new OrganizationKnowledgeSnapshot(tenantId,schemaVersion,revision,origin,value,structured,digest);}
    public OrganizationKnowledgeSnapshot withStructured(StructuredKnowledgeSettings value){return new OrganizationKnowledgeSnapshot(tenantId,schemaVersion,revision,origin,documents,value,digest);}
    public OrganizationKnowledgeSnapshot withDigest(String value){return new OrganizationKnowledgeSnapshot(tenantId,schemaVersion,revision,origin,documents,structured,value);}
}
