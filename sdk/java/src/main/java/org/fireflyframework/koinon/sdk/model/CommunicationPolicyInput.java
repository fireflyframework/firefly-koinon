// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CommunicationPolicyInput contract. */
public record CommunicationPolicyInput(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("sender_id") JsonField<String> senderId,
    @JsonProperty("rules") List<NotificationPreferenceRuleInput> rules,
    @JsonProperty("digest_enabled") Boolean digestEnabled,
    @JsonProperty("allowed_digests") List<CommunicationPolicyAllowedDigests> allowedDigests,
    @JsonProperty("default_digest") CommunicationPolicyAllowedDigests defaultDigest,
    @JsonProperty("default_schedule") DigestSchedule defaultSchedule,
    @JsonProperty("admin_summaries") List<AdministrativeSummarySchedule> adminSummaries,
    @JsonProperty("default_locale") JsonField<String> defaultLocale
) {
    public CommunicationPolicyInput {
        rules=rules==null?null:List.copyOf(rules);
        allowedDigests=allowedDigests==null?null:List.copyOf(allowedDigests);
        adminSummaries=adminSummaries==null?null:List.copyOf(adminSummaries);
    }

    public static CommunicationPolicyInput empty(){return new CommunicationPolicyInput(null,null,null,null,null,null,null,null,null);}
    public CommunicationPolicyInput withExpectedRevision(Long value){return new CommunicationPolicyInput(value,senderId,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withSenderId(String value){return new CommunicationPolicyInput(expectedRevision,JsonField.of(value),rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput clearSenderId(){return new CommunicationPolicyInput(expectedRevision,JsonField.clear(),rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput omitSenderId(){return new CommunicationPolicyInput(expectedRevision,null,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withRules(List<NotificationPreferenceRuleInput> value){return new CommunicationPolicyInput(expectedRevision,senderId,value,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withDigestEnabled(Boolean value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,value,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withAllowedDigests(List<CommunicationPolicyAllowedDigests> value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,value,defaultDigest,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withDefaultDigest(CommunicationPolicyAllowedDigests value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,value,defaultSchedule,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withDefaultSchedule(DigestSchedule value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,defaultDigest,value,adminSummaries,defaultLocale);}
    public CommunicationPolicyInput withAdminSummaries(List<AdministrativeSummarySchedule> value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,value,defaultLocale);}
    public CommunicationPolicyInput withDefaultLocale(String value){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,JsonField.of(value));}
    public CommunicationPolicyInput clearDefaultLocale(){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,JsonField.clear());}
    public CommunicationPolicyInput omitDefaultLocale(){return new CommunicationPolicyInput(expectedRevision,senderId,rules,digestEnabled,allowedDigests,defaultDigest,defaultSchedule,adminSummaries,null);}
}
