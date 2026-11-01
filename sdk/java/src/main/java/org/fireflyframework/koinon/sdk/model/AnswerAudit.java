// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AnswerAudit contract. */
public record AnswerAudit(
    @JsonProperty("run_id") String runId,
    @JsonProperty("provenance_status") AnswerAuditProvenanceStatus provenanceStatus,
    @JsonProperty("source_provenance_complete") Boolean sourceProvenanceComplete,
    @JsonProperty("output_release") AnswerRelease outputRelease,
    @JsonProperty("knowledge_settings_snapshot") OrganizationKnowledgeSnapshot knowledgeSettingsSnapshot,
    @JsonProperty("memory") MemoryReceipt memory,
    @JsonProperty("generations") List<GenerationReceipt> generations,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("private_files") List<PrivateFileReceipt> privateFiles,
    @JsonProperty("native_reads") List<NativeReadReceipt> nativeReads,
    @JsonProperty("sql_attempts") List<SqlAttemptReceipt> sqlAttempts,
    @JsonProperty("rlm_tools") List<RlmToolReceipt> rlmTools
) {
    public AnswerAudit(String runId, AnswerAuditProvenanceStatus provenanceStatus, Boolean sourceProvenanceComplete, OrganizationKnowledgeSnapshot knowledgeSettingsSnapshot, MemoryReceipt memory, List<GenerationReceipt> generations, List<SourceReference> sources, List<PrivateFileReceipt> privateFiles, List<NativeReadReceipt> nativeReads, List<SqlAttemptReceipt> sqlAttempts, List<RlmToolReceipt> rlmTools){this(runId,provenanceStatus,sourceProvenanceComplete,null,knowledgeSettingsSnapshot,memory,generations,sources,privateFiles,nativeReads,sqlAttempts,rlmTools);}
    public AnswerAudit(String runId, AnswerAuditProvenanceStatus provenanceStatus, Boolean sourceProvenanceComplete, OrganizationKnowledgeSnapshot knowledgeSettingsSnapshot, List<GenerationReceipt> generations, List<SourceReference> sources, List<PrivateFileReceipt> privateFiles, List<NativeReadReceipt> nativeReads, List<SqlAttemptReceipt> sqlAttempts, List<RlmToolReceipt> rlmTools){this(runId,provenanceStatus,sourceProvenanceComplete,null,knowledgeSettingsSnapshot,null,generations,sources,privateFiles,nativeReads,sqlAttempts,rlmTools);}
    public AnswerAudit {
        generations=generations==null?null:List.copyOf(generations);
        sources=sources==null?null:List.copyOf(sources);
        privateFiles=privateFiles==null?null:List.copyOf(privateFiles);
        nativeReads=nativeReads==null?null:List.copyOf(nativeReads);
        sqlAttempts=sqlAttempts==null?null:List.copyOf(sqlAttempts);
        rlmTools=rlmTools==null?null:List.copyOf(rlmTools);
    }

}
