// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ProfileUpdate contract. */
public record ProfileUpdate(
    @JsonProperty("initialize_only") Boolean initializeOnly,
    @JsonProperty("display_name") JsonField<String> displayName,
    @JsonProperty("locale") JsonField<String> locale,
    @JsonProperty("time_zone") JsonField<String> timeZone,
    @JsonProperty("response_language") JsonField<String> responseLanguage
) {
    public ProfileUpdate(JsonField<String> displayName, JsonField<String> locale, JsonField<String> timeZone, JsonField<String> responseLanguage){this(null,displayName,locale,timeZone,responseLanguage);}

    public static ProfileUpdate empty(){return new ProfileUpdate(null,null,null,null,null);}
    public ProfileUpdate withInitializeOnly(Boolean value){return new ProfileUpdate(value,displayName,locale,timeZone,responseLanguage);}
    public ProfileUpdate withDisplayName(String value){return new ProfileUpdate(initializeOnly,JsonField.of(value),locale,timeZone,responseLanguage);}
    public ProfileUpdate clearDisplayName(){return new ProfileUpdate(initializeOnly,JsonField.clear(),locale,timeZone,responseLanguage);}
    public ProfileUpdate omitDisplayName(){return new ProfileUpdate(initializeOnly,null,locale,timeZone,responseLanguage);}
    public ProfileUpdate withLocale(String value){return new ProfileUpdate(initializeOnly,displayName,JsonField.of(value),timeZone,responseLanguage);}
    public ProfileUpdate clearLocale(){return new ProfileUpdate(initializeOnly,displayName,JsonField.clear(),timeZone,responseLanguage);}
    public ProfileUpdate omitLocale(){return new ProfileUpdate(initializeOnly,displayName,null,timeZone,responseLanguage);}
    public ProfileUpdate withTimeZone(String value){return new ProfileUpdate(initializeOnly,displayName,locale,JsonField.of(value),responseLanguage);}
    public ProfileUpdate clearTimeZone(){return new ProfileUpdate(initializeOnly,displayName,locale,JsonField.clear(),responseLanguage);}
    public ProfileUpdate omitTimeZone(){return new ProfileUpdate(initializeOnly,displayName,locale,null,responseLanguage);}
    public ProfileUpdate withResponseLanguage(String value){return new ProfileUpdate(initializeOnly,displayName,locale,timeZone,JsonField.of(value));}
    public ProfileUpdate clearResponseLanguage(){return new ProfileUpdate(initializeOnly,displayName,locale,timeZone,JsonField.clear());}
    public ProfileUpdate omitResponseLanguage(){return new ProfileUpdate(initializeOnly,displayName,locale,timeZone,null);}
}
