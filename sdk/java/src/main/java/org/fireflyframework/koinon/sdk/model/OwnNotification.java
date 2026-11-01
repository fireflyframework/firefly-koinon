// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical OwnNotification contract. */
public record OwnNotification(
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("actor_name") String actorName,
    @JsonProperty("details") NotificationDetails details,
    @JsonProperty("id") String id,
    @JsonProperty("kind") DeliveryRecordKind kind,
    @JsonProperty("title") String title,
    @JsonProperty("body") String body,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("read_at") Instant readAt,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("organization_name") String organizationName,
    @JsonProperty("target") NotificationTarget target,
    @JsonProperty("effective_locale") String effectiveLocale,
    @JsonProperty("locale_origin") CommunicationCapabilitiesLocaleOrigin localeOrigin,
    @JsonProperty("powered_by") EmailPreviewPoweredBy poweredBy,
    @JsonProperty("copyright") String copyright
) {

}
