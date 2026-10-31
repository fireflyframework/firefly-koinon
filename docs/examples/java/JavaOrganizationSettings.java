// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaOrganizationSettings {
    public static ModelProvider renameProvider(KoinonClient client, String tenant,
            String providerId, String name) {
        return client.providers(tenant).update(providerId, ProviderInput.empty().withName(name));
    }

    public static OrganizationChatSettings setDefaultAgent(KoinonClient client,
            String tenant, OrganizationChatSettings reviewed, String agentId) {
        return client.organizationChat(tenant).update(OrganizationChatSettingsInput.empty()
            .withExpectedRevision(reviewed.revision()).withDefaultAgentId(agentId));
    }

    public static OrganizationKnowledgeSettings setDocumentMode(KoinonClient client,
            String tenant, OrganizationKnowledgeSettings reviewed, KnowledgeAnswerMode mode) {
        return client.organizationKnowledge(tenant).update(OrganizationKnowledgeSettingsInput.empty()
            .withExpectedRevision(reviewed.revision())
            .withDocuments(reviewed.documents().withAnswerMode(mode))
            .withStructured(reviewed.structured()));
    }
}
