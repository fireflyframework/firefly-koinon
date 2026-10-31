// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaRuns {
    public static ChatRun submit(KoinonClient client, String tenant,
            KnowledgeScope scope, String question, String stableRequestId) {
        var defaults = client.organizationChat(tenant).get(OrganizationChatFilter.empty()
            .withWorkspaceId(scope.workspaceId()).withProjectId(scope.projectId()));
        if (!Boolean.TRUE.equals(defaults.canRun()) || defaults.defaultAgentId() == null) {
            throw new IllegalStateException("An operator must configure an available chat agent");
        }
        var thread = client.chat(tenant).createThread(ThreadInput.empty()
            .withTitle("Knowledge question").withScope(scope));
        return client.chat(tenant).submit(thread.id(), RunInput.empty()
            .withAgentId(defaults.defaultAgentId()).withScope(scope).withMessage(question)
            .withClientRequestId(stableRequestId).withAttachmentIds(List.of()));
    }

    public static ChatRun cancelProcessing(KoinonClient client, String tenant, String runId) {
        return client.chat(tenant).cancel(runId);
    }
}
