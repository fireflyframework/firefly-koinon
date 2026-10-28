// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical GlossaryTermCreate contract. */
public record GlossaryTermCreate(
    @JsonProperty("term") String term,
    @JsonProperty("definition") String definition,
    @JsonProperty("synonyms") List<String> synonyms,
    @JsonProperty("tags") List<String> tags,
    @JsonProperty("related_columns") List<String> relatedColumns,
    @JsonProperty("related_metrics") List<String> relatedMetrics
) {
    public GlossaryTermCreate {
        synonyms=synonyms==null?null:List.copyOf(synonyms);
        tags=tags==null?null:List.copyOf(tags);
        relatedColumns=relatedColumns==null?null:List.copyOf(relatedColumns);
        relatedMetrics=relatedMetrics==null?null:List.copyOf(relatedMetrics);
    }

    public static GlossaryTermCreate empty(){return new GlossaryTermCreate(null,null,null,null,null,null);}
    public GlossaryTermCreate withTerm(String value){return new GlossaryTermCreate(value,definition,synonyms,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermCreate withDefinition(String value){return new GlossaryTermCreate(term,value,synonyms,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermCreate withSynonyms(List<String> value){return new GlossaryTermCreate(term,definition,value,tags,relatedColumns,relatedMetrics);}
    public GlossaryTermCreate withTags(List<String> value){return new GlossaryTermCreate(term,definition,synonyms,value,relatedColumns,relatedMetrics);}
    public GlossaryTermCreate withRelatedColumns(List<String> value){return new GlossaryTermCreate(term,definition,synonyms,tags,value,relatedMetrics);}
    public GlossaryTermCreate withRelatedMetrics(List<String> value){return new GlossaryTermCreate(term,definition,synonyms,tags,relatedColumns,value);}
}
