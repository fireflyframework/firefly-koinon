// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaAdministration {
    private JavaAdministration() {}

    public static ModelProvider createProvider(KoinonClient client, String tenant,
            ProviderInput reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review provider configuration");
        return client.providers(tenant).create(reviewed);
    }

    public static AgentConfiguration createReader(KoinonClient client, String tenant,
            String providerId, String modelId, KnowledgeScope scope, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review agent model, tools and scope");
        return client.agents(tenant).create(AgentInput.empty()
            .withName("Knowledge reader").withProviderId(providerId).withModelId(modelId)
            .withScope(scope).withTools(List.of(AgentTool.SEARCH_KNOWLEDGE,
                AgentTool.INSPECT_SCHEMA, AgentTool.QUERY_DATASET)).withEnabled(true));
    }

    public static KnowledgeModeTransitionView prepareDocumentMode(KoinonClient client, String tenant,
            OrganizationKnowledgeSettings reviewed, KnowledgeAnswerMode mode,
            String idempotencyKey, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review the mode and retained settings");
        return client.knowledgeModes(tenant).create(OrganizationKnowledgeSettingsInput.empty()
            .withExpectedRevision(reviewed.revision())
            .withDocuments(reviewed.documents().withAnswerMode(mode))
            .withStructured(reviewed.structured()), idempotencyKey);
    }

    public static Membership updateMember(KoinonClient client, String tenant,
            String memberId, MemberUpdate reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Review the member and access change");
        return client.members(tenant).update(memberId, reviewed);
    }
}
