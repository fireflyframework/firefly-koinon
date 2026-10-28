// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProfileUpdate contract. */
public record ProfileUpdate(
    @JsonProperty("display_name") JsonField<String> displayName,
    @JsonProperty("locale") JsonField<String> locale,
    @JsonProperty("time_zone") JsonField<String> timeZone,
    @JsonProperty("response_language") JsonField<String> responseLanguage
) {

    public static ProfileUpdate empty(){return new ProfileUpdate(null,null,null,null);}
    public ProfileUpdate withDisplayName(String value){return new ProfileUpdate(JsonField.of(value),locale,timeZone,responseLanguage);}
    public ProfileUpdate clearDisplayName(){return new ProfileUpdate(JsonField.clear(),locale,timeZone,responseLanguage);}
    public ProfileUpdate omitDisplayName(){return new ProfileUpdate(null,locale,timeZone,responseLanguage);}
    public ProfileUpdate withLocale(String value){return new ProfileUpdate(displayName,JsonField.of(value),timeZone,responseLanguage);}
    public ProfileUpdate clearLocale(){return new ProfileUpdate(displayName,JsonField.clear(),timeZone,responseLanguage);}
    public ProfileUpdate omitLocale(){return new ProfileUpdate(displayName,null,timeZone,responseLanguage);}
    public ProfileUpdate withTimeZone(String value){return new ProfileUpdate(displayName,locale,JsonField.of(value),responseLanguage);}
    public ProfileUpdate clearTimeZone(){return new ProfileUpdate(displayName,locale,JsonField.clear(),responseLanguage);}
    public ProfileUpdate omitTimeZone(){return new ProfileUpdate(displayName,locale,null,responseLanguage);}
    public ProfileUpdate withResponseLanguage(String value){return new ProfileUpdate(displayName,locale,timeZone,JsonField.of(value));}
    public ProfileUpdate clearResponseLanguage(){return new ProfileUpdate(displayName,locale,timeZone,JsonField.clear());}
    public ProfileUpdate omitResponseLanguage(){return new ProfileUpdate(displayName,locale,timeZone,null);}
}
