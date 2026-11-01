// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical NotificationPreferencesInput contract. */
public record NotificationPreferencesInput(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("rules") List<NotificationPreferenceRuleInput> rules,
    @JsonProperty("digest") CommunicationPolicyAllowedDigests digest,
    @JsonProperty("schedule") DigestSchedule schedule,
    @JsonProperty("admin_summaries") JsonField<Boolean> adminSummaries,
    @JsonProperty("notification_locale") JsonField<String> notificationLocale
) {
    public NotificationPreferencesInput {
        rules=rules==null?null:List.copyOf(rules);
    }

    public static NotificationPreferencesInput empty(){return new NotificationPreferencesInput(null,null,null,null,null,null);}
    public NotificationPreferencesInput withExpectedRevision(Long value){return new NotificationPreferencesInput(value,rules,digest,schedule,adminSummaries,notificationLocale);}
    public NotificationPreferencesInput withRules(List<NotificationPreferenceRuleInput> value){return new NotificationPreferencesInput(expectedRevision,value,digest,schedule,adminSummaries,notificationLocale);}
    public NotificationPreferencesInput withDigest(CommunicationPolicyAllowedDigests value){return new NotificationPreferencesInput(expectedRevision,rules,value,schedule,adminSummaries,notificationLocale);}
    public NotificationPreferencesInput withSchedule(DigestSchedule value){return new NotificationPreferencesInput(expectedRevision,rules,digest,value,adminSummaries,notificationLocale);}
    public NotificationPreferencesInput withAdminSummaries(Boolean value){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,JsonField.of(value),notificationLocale);}
    public NotificationPreferencesInput clearAdminSummaries(){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,JsonField.clear(),notificationLocale);}
    public NotificationPreferencesInput omitAdminSummaries(){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,null,notificationLocale);}
    public NotificationPreferencesInput withNotificationLocale(String value){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,adminSummaries,JsonField.of(value));}
    public NotificationPreferencesInput clearNotificationLocale(){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,adminSummaries,JsonField.clear());}
    public NotificationPreferencesInput omitNotificationLocale(){return new NotificationPreferencesInput(expectedRevision,rules,digest,schedule,adminSummaries,null);}
}
