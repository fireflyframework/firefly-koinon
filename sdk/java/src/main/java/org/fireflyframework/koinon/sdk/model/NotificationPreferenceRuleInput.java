// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NotificationPreferenceRuleInput contract. */
public record NotificationPreferenceRuleInput(
    @JsonProperty("kind") DeliveryRecordKind kind,
    @JsonProperty("inbox") Boolean inbox,
    @JsonProperty("email") Boolean email
) {

    public static NotificationPreferenceRuleInput empty(){return new NotificationPreferenceRuleInput(null,null,null);}
    public NotificationPreferenceRuleInput withKind(DeliveryRecordKind value){return new NotificationPreferenceRuleInput(value,inbox,email);}
    public NotificationPreferenceRuleInput withInbox(Boolean value){return new NotificationPreferenceRuleInput(kind,value,email);}
    public NotificationPreferenceRuleInput withEmail(Boolean value){return new NotificationPreferenceRuleInput(kind,inbox,value);}
}
