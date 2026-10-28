// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical GlossaryTermUpdate contract. */
public record GlossaryTermUpdate(
    @JsonProperty("definition") JsonField<String> definition,
    @JsonProperty("synonyms") JsonField<List<String>> synonyms,
    @JsonProperty("tags") JsonField<List<String>> tags,
    @JsonProperty("related_columns") JsonField<List<String>> relatedColumns,
    @JsonProperty("related_metrics") JsonField<List<String>> relatedMetrics
) {

    public static GlossaryTermUpdate empty(){return new GlossaryTermUpdate(null,null,null,null,null);}
    public GlossaryTermUpdate withDefinition(String value){return new GlossaryTermUpdate(JsonField.of(value),synonyms,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate clearDefinition(){return new GlossaryTermUpdate(JsonField.clear(),synonyms,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate omitDefinition(){return new GlossaryTermUpdate(null,synonyms,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate withSynonyms(List<String> value){return new GlossaryTermUpdate(definition,JsonField.of(value),tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate clearSynonyms(){return new GlossaryTermUpdate(definition,JsonField.clear(),tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate omitSynonyms(){return new GlossaryTermUpdate(definition,null,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate withTags(List<String> value){return new GlossaryTermUpdate(definition,synonyms,JsonField.of(value),relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate clearTags(){return new GlossaryTermUpdate(definition,synonyms,JsonField.clear(),relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate omitTags(){return new GlossaryTermUpdate(definition,synonyms,null,relatedColumns,relatedMetrics);}
    public GlossaryTermUpdate withRelatedColumns(List<String> value){return new GlossaryTermUpdate(definition,synonyms,tags,JsonField.of(value),relatedMetrics);}
    public GlossaryTermUpdate clearRelatedColumns(){return new GlossaryTermUpdate(definition,synonyms,tags,JsonField.clear(),relatedMetrics);}
    public GlossaryTermUpdate omitRelatedColumns(){return new GlossaryTermUpdate(definition,synonyms,tags,null,relatedMetrics);}
    public GlossaryTermUpdate withRelatedMetrics(List<String> value){return new GlossaryTermUpdate(definition,synonyms,tags,relatedColumns,JsonField.of(value));}
    public GlossaryTermUpdate clearRelatedMetrics(){return new GlossaryTermUpdate(definition,synonyms,tags,relatedColumns,JsonField.clear());}
    public GlossaryTermUpdate omitRelatedMetrics(){return new GlossaryTermUpdate(definition,synonyms,tags,relatedColumns,null);}
}
