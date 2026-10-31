// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;
import static org.junit.jupiter.api.Assertions.*;
import java.util.Arrays;
import java.util.List;
import org.fireflyframework.koinon.sdk.model.RlmToolReceipt;
import org.junit.jupiter.api.Test;
final class CuratedRlmReceiptTest {
 @Test void retainsOldConstructorAndAbsentKnowledgeScope() throws Exception {
  assertTrue(Arrays.stream(RlmToolReceipt.class.getConstructors()).anyMatch(c->c.getParameterCount()==16));
  var value=new JsonCodec().mapper.readValue("{\"source_ids\":[\"document\"]}",RlmToolReceipt.class);
  assertEquals(List.of("document"),value.sourceIds());assertEquals(List.of(),value.knowledgeItemIds());
 }
 @Test void knowledgeOnlyScopeRemainsSeparateAndDefensive() throws Exception {
  var codec=new JsonCodec();var value=codec.mapper.readValue("{\"knowledge_item_ids\":[\"canonical-item\"]}",RlmToolReceipt.class);
  assertEquals(List.of(),value.sourceIds());assertEquals(List.of("canonical-item"),value.knowledgeItemIds());
  assertThrows(UnsupportedOperationException.class,()->value.knowledgeItemIds().add("other"));
  var json=codec.tree(codec.encode(value));assertEquals("canonical-item",json.path("knowledge_item_ids").get(0).asText());
 }
}
