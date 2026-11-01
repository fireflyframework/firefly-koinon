// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical EmailPreview contract. */
public record EmailPreview(
    @JsonProperty("subject") String subject,
    @JsonProperty("sender_name") String senderName,
    @JsonProperty("recipient_display_name") String recipientDisplayName,
    @JsonProperty("recipient_email") String recipientEmail,
    @JsonProperty("heading") String heading,
    @JsonProperty("paragraphs") List<String> paragraphs,
    @JsonProperty("action_label") String actionLabel,
    @JsonProperty("footer") String footer,
    @JsonProperty("product_name") String productName,
    @JsonProperty("accent_color") String accentColor,
    @JsonProperty("branding") BrandingValues branding,
    @JsonProperty("rendered_html") String renderedHtml,
    @JsonProperty("rendered_text") String renderedText,
    @JsonProperty("usage_summary") CommunicationUsageSummary usageSummary,
    @JsonProperty("activity_summary") ActivitySummary activitySummary,
    @JsonProperty("organization_name") String organizationName,
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("effective_locale") String effectiveLocale,
    @JsonProperty("locale_origin") CommunicationCapabilitiesLocaleOrigin localeOrigin,
    @JsonProperty("powered_by") EmailPreviewPoweredBy poweredBy,
    @JsonProperty("copyright") String copyright
) {
    public EmailPreview {
        paragraphs=paragraphs==null?null:List.copyOf(paragraphs);
    }

}
