// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.internal;

import static org.junit.jupiter.api.Assertions.*;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.time.Instant;
import java.util.stream.Stream;
import org.fireflyframework.koinon.sdk.model.*;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;

final class CanonicalModelTest {
  private final JsonCodec codec = new JsonCodec();

  private JsonNode fixtures() throws Exception {
    try (var input = getClass().getResourceAsStream("/canonical-model-fixtures.json")) {
      return codec.tree(input.readAllBytes());
    }
  }

  @TestFactory
  Stream<DynamicTest> allCanonicalJsonDefinitionsRoundTrip() throws Exception {
    var data = fixtures();
    assertEquals(
        data.path("fixtures").size() + data.path("excluded_definitions").size(),
        data.path("definition_count").asInt());
    var excluded = new java.util.HashSet<String>();
    data.path("excluded_definitions").forEach(value -> excluded.add(value.asText()));
    assertEquals(
        java.util.Set.of(
            "AttachmentUpload",
            "DatasetFileUpload",
            "AvatarUpload",
            "BinaryDownload",
            "DocumentReplacement",
            "JsonValue",
            "SourceUpload",
            "TableReplacement"),
        excluded);
    return data.path("fixtures").properties().stream()
        .map(
            entry ->
                DynamicTest.dynamicTest(
                    entry.getKey(),
                    () -> {
                      String name = entry.getKey();
                      var expected = entry.getValue();
                      com.fasterxml.jackson.databind.JavaType type;
                      if (name.startsWith("Page_"))
                        type =
                            codec
                                .mapper
                                .getTypeFactory()
                                .constructParametricType(
                                    Page.class,
                                    Class.forName(
                                        "org.fireflyframework.koinon.sdk.model."
                                            + name.substring(5, name.length() - 1)));
                      else
                        type =
                            codec.type(
                                Class.forName("org.fireflyframework.koinon.sdk.model." + name));
                      Object model = codec.decode(codec.encode(expected), type);
                      assertEquals(
                          expected,
                          codec.tree(codec.encode(model)),
                          name + " fields, references and enum values must survive typed JSON");
                    }));
  }

  @TestFactory
  Stream<DynamicTest> everyDeclaredWireEnumValueRoundTrips() throws Exception {
    JsonNode enums;
    try (var input = getClass().getResourceAsStream("/canonical-enums.json")) {
      enums = codec.tree(input.readAllBytes());
    }
    return enums.properties().stream()
        .flatMap(
            entry ->
                java.util.stream.StreamSupport.stream(entry.getValue().spliterator(), false)
                    .map(
                        value ->
                            DynamicTest.dynamicTest(
                                entry.getKey() + "." + value.asText(),
                                () -> {
                                  var type =
                                      codec.type(
                                          Class.forName(
                                              "org.fireflyframework.koinon.sdk.model."
                                                  + entry.getKey()));
                                  Object model = codec.decode(codec.encode(value), type);
                                  assertEquals(value, codec.tree(codec.encode(model)));
                                })));
  }

  @Test
  void patchAbsenceExplicitNullAndFalseRemainDistinct() throws Exception {
    var omitted = codec.tree(codec.encode(ProviderInput.empty()));
    assertFalse(omitted.has("secret"));
    var clear = codec.tree(codec.encode(ProviderInput.empty().clearSecret().withEnabled(false)));
    assertTrue(clear.has("secret"));
    assertTrue(clear.get("secret").isNull());
    assertFalse(clear.get("enabled").asBoolean());
    ProviderInput absent =
        codec.decode(
            "{}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
            codec.type(ProviderInput.class));
    assertNull(absent.secret());
    ProviderInput explicit =
        codec.decode(
            "{\"secret\":null}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
            codec.type(ProviderInput.class));
    assertNotNull(explicit.secret());
    assertNull(explicit.secret().value());
    assertFalse(
        ProviderInput.empty().withSecret("private-value").toString().contains("private-value"));
  }

  @Test
  void timestampsAndOpaquePrecisionRemainExactAndDefensive() throws Exception {
    var value = fixtures().path("fixtures").path("CatalogEntry");
    CatalogEntry entry = codec.decode(codec.encode(value), codec.type(CatalogEntry.class));
    assertEquals(Instant.parse("2026-10-27T12:34:56Z"), entry.createdAt());
    var original = (ObjectNode) entry.metadata();
    original.put("intruder", true);
    assertFalse(entry.metadata().has("intruder"));
    assertEquals(
        "12345678901234567890.12345678901234567890",
        entry.metadata().path("example").path("decimal").asText());
    var source =
        (ObjectNode)
            codec.tree(
                "{\"amount\":\"99999999999999999.123456789\"}"
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8));
    var field = JsonField.of((JsonNode) source);
    source.put("amount", "changed");
    assertEquals("99999999999999999.123456789", field.value().get("amount").asText());
    ((ObjectNode) field.value()).put("amount", "changed-again");
    assertEquals("99999999999999999.123456789", field.value().get("amount").asText());
  }

  @Test
  void absentRequiredPageItemsAreRejected() {
    assertThrows(
        IllegalStateException.class,
        () ->
            codec.decode(
                "{}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                codec
                    .mapper
                    .getTypeFactory()
                    .constructParametricType(Page.class, CatalogEntry.class)));
  }

  @Test
  void evidenceDataIsTypedAndEnumUnknownValuesFail() throws Exception {
    for (var pair :
        java.util.Map.of(
                "search",
                SearchResponse.class,
                "query",
                QueryResponse.class,
                "schema",
                DatasetSchema.class,
                "lineage",
                Lineage.class)
            .entrySet()) {
      var envelope =
          codec
              .mapper
              .createObjectNode()
              .put("id", "result")
              .put("run_id", "run")
              .put("kind", pair.getKey());
      envelope.set("data", fixtures().path("fixtures").path(pair.getValue().getSimpleName()));
      EvidenceResult result =
          codec.decode(codec.encode(envelope), codec.type(EvidenceResult.class));
      assertEquals(pair.getKey(), result.kind().value());
      assertEquals(envelope, codec.tree(codec.encode(result)));
    }
    assertThrows(
        IllegalStateException.class,
        () ->
            codec.decode(
                "\"unknown-model-api\"".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                codec.type(ModelApi.class)));
  }
}
