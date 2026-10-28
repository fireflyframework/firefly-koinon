// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.model.DocumentReplacement;
import org.fireflyframework.koinon.sdk.model.SourceUpload;

final class ApiSupport {
  private ApiSupport() {}

  static String precondition(String revision) {
    Objects.requireNonNull(revision, "expected revision is required");
    if (revision.isBlank()
        || revision.indexOf('"') >= 0
        || revision.chars().anyMatch(c -> c < 33 || c == 127))
      throw new IllegalArgumentException(
          "Expected revision must be an unquoted digest or snapshot identifier");
    return "\"" + revision + "\"";
  }

  static Map<String, String> uploadFields(SourceUpload input) {
    var fields = new LinkedHashMap<String, String>();
    fields.put("workspace_id", input.workspaceId());
    fields.put("project_id", input.projectId());
    fields.put("parent_id", input.parentId());
    fields.put("mode", input.mode().value());
    return Map.copyOf(fields);
  }

  static Map<String, String> replacementFields(DocumentReplacement input) {
    return input.acknowledgeChunkInvalidation() == null
        ? Map.of()
        : Map.of("acknowledge_chunk_invalidation", input.acknowledgeChunkInvalidation().toString());
  }
}
