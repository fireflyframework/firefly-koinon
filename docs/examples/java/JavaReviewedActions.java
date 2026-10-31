// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaReviewedActions {
    public static ExportReview reviewExport(KoinonClient client, String tenant,
            String threadId, List<String> selectedMessageIds) {
        return client.exports(tenant).review(ConversationExportInput.empty()
            .withKind(ConversationExportInputKind.CONVERSATION)
            .withFormat(ConversationExportInputFormat.MARKDOWN)
            .withThreadId(threadId).withMessageIds(selectedMessageIds).withIncludeEvidence(true));
    }

    public static org.fireflyframework.koinon.sdk.model.Export createReviewedExport(
            KoinonClient client, String tenant, ExportReview reviewed, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.exports(tenant).create(ExportCreate.empty()
            .withReviewId(reviewed.id()).withExpectedRevision(reviewed.revision()));
    }

    public static ShareReview reviewShare(KoinonClient client, String tenant,
            String threadId, List<String> selectedMessageIds) {
        return client.shares(tenant).review(ShareReviewInput.empty()
            .withThreadId(threadId).withMessageIds(selectedMessageIds));
    }

    public static Share createReviewedShare(KoinonClient client, String tenant,
            ShareReview reviewed, int expiresInHours, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.shares(tenant).create(ShareCreate.empty()
            .withReviewId(reviewed.id()).withExpectedRevision(reviewed.revision())
            .withRecipientPolicy(reviewed.recipientPolicy()).withExpiresInHours(expiresInHours));
    }

    public static CatalogProposal confirmReviewedProposal(KoinonClient client, String tenant,
            String runId, String proposalId, long reviewedRevision, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.chatProposals(tenant).confirm(runId, proposalId,
            ProposalConfirmation.empty().withConfirm(true).withExpectedRevision(reviewedRevision));
    }
}
