// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationKnowledgeSettingsInput contract. */
public record OrganizationKnowledgeSettingsInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("documents") DocumentKnowledgeSettings documents,
    @JsonProperty("structured") StructuredKnowledgeSettings structured
) {

    public static OrganizationKnowledgeSettingsInput empty(){return new OrganizationKnowledgeSettingsInput(null,null,null);}
    public OrganizationKnowledgeSettingsInput withExpectedRevision(Integer value){return new OrganizationKnowledgeSettingsInput(value,documents,structured);}
    public OrganizationKnowledgeSettingsInput withDocuments(DocumentKnowledgeSettings value){return new OrganizationKnowledgeSettingsInput(expectedRevision,value,structured);}
    public OrganizationKnowledgeSettingsInput withStructured(StructuredKnowledgeSettings value){return new OrganizationKnowledgeSettingsInput(expectedRevision,documents,value);}
}
