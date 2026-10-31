// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaCuratedKnowledge {
    public static KnowledgeIntent previewDraft(KoinonClient client, String tenant,
            String destinationId, KnowledgeContent content) {
        return client.knowledgeIntents(tenant).preview(KnowledgeIntentInput.empty()
            .withAction(ExternalReviewInputAction.CREATE_DRAFT)
            .withDestinationId(destinationId).withContent(content)
            .withOrigin(new UserStatementOrigin(UserStatementEvidenceKind.USER_STATEMENT)));
    }

    public static KnowledgeCommitOutcome confirmReviewed(KoinonClient client, String tenant,
            String intentId, long reviewedRevision, String reviewedDigest,
            String stableRequestId, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.knowledgeIntents(tenant).confirm(intentId, KnowledgeConfirmation.empty()
            .withConfirm(true).withExpectedRevision(reviewedRevision)
            .withAuthorizationDigest(reviewedDigest), stableRequestId);
    }
}
