// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ReplacementMemberInput contract. */
public record ReplacementMemberInput(
    @JsonProperty("new_locator") String newLocator,
    @JsonProperty("previous_table_id") JsonField<String> previousTableId
) {

    public static ReplacementMemberInput empty(){return new ReplacementMemberInput(null,null);}
    public ReplacementMemberInput withNewLocator(String value){return new ReplacementMemberInput(value,previousTableId);}
    public ReplacementMemberInput withPreviousTableId(String value){return new ReplacementMemberInput(newLocator,JsonField.of(value));}
    public ReplacementMemberInput clearPreviousTableId(){return new ReplacementMemberInput(newLocator,JsonField.clear());}
    public ReplacementMemberInput omitPreviousTableId(){return new ReplacementMemberInput(newLocator,null);}
}
