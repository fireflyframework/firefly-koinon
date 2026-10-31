# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compile and run an external consumer using the built JAR and runtime dependencies."""

import os
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / "sdk/java"


def main() -> None:
    archives = list((SDK / "target").glob("koinon-sdk-*.jar"))
    archives = [
        path
        for path in archives
        if not path.name.endswith(("-sources.jar", "-javadoc.jar"))
    ]
    if len(archives) != 1:
        raise SystemExit("Build one SDK JAR with Maven before checking its consumer")
    archive = archives[0]
    with zipfile.ZipFile(archive) as package:
        for name in ("LICENSE", "NOTICE"):
            assert package.read("META-INF/" + name) == (ROOT / name).read_bytes()
        classes = [name for name in package.namelist() if name.endswith(".class")]
        assert classes and all(
            struct.unpack(">H", package.read(name)[6:8])[0] == 65 for name in classes
        )
    with tempfile.TemporaryDirectory(prefix="koinon-java-consumer-") as directory:
        consumer = Path(directory)
        classpath_file = consumer / "classpath.txt"
        subprocess.run(
            [
                "mvn",
                "--batch-mode",
                "--no-transfer-progress",
                "-q",
                "-f",
                str(SDK / "pom.xml"),
                "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath",
                "-DincludeScope=runtime",
                "-Dmdep.outputFile=" + str(classpath_file),
            ],
            check=True,
            timeout=120,
        )
        classpath = str(archive) + os.pathsep + classpath_file.read_text().strip()
        source = consumer / "HeadlessConsumer.java"
        source.write_text("""import java.net.URI;
import java.math.BigDecimal;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.ExactValues;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.api.DatasetsApi;
import org.fireflyframework.koinon.sdk.api.OrganizationChatApi;
import org.fireflyframework.koinon.sdk.api.OrganizationKnowledgeApi;
import org.fireflyframework.koinon.sdk.model.OrganizationKnowledgeSettings;
import org.fireflyframework.koinon.sdk.model.OrganizationKnowledgeSettingsInput;
import org.fireflyframework.koinon.sdk.model.OrganizationKnowledgeSnapshot;
import org.fireflyframework.koinon.sdk.model.KnowledgeAnswerMode;
import org.fireflyframework.koinon.sdk.model.OrganizationChatSettings;
import org.fireflyframework.koinon.sdk.model.OrganizationChatSettingsInput;
import org.fireflyframework.koinon.sdk.model.OrganizationChatFilter;
import org.fireflyframework.koinon.sdk.model.DatasetFileAppendResult;
import org.fireflyframework.koinon.sdk.model.DatasetFileUpload;
import org.fireflyframework.koinon.sdk.api.OrganizationPeopleApi;
import org.fireflyframework.koinon.sdk.model.OrganizationPeopleFilter;
import org.fireflyframework.koinon.sdk.model.OrganizationPerson;
import org.fireflyframework.koinon.sdk.model.OrganizationPersonPatch;
public final class HeadlessConsumer {
  static OrganizationPerson positionSignature(OrganizationPeopleApi directory) {
    var page = directory.list(OrganizationPeopleFilter.empty()
        .withQ("Alex").withPage(1).withPageSize(25));
    var person = page.items().stream()
        .filter(item -> item.id() != null).findFirst().orElseThrow();
    return directory.update(person.id(), OrganizationPersonPatch.empty()
        .withExpectedRevision(person.revision())
        .withJobTitle("Knowledge Operations Lead").clearManagerId());
  }
  static OrganizationKnowledgeSettings policySignature(OrganizationKnowledgeApi api) {
    var current = api.get();
    return api.update(OrganizationKnowledgeSettingsInput.empty()
        .withExpectedRevision(current.revision())
        .withDocuments(current.documents().withAnswerMode(KnowledgeAnswerMode.RAG))
        .withStructured(current.structured()));
  }
  static OrganizationKnowledgeSnapshot captured(org.fireflyframework.koinon.sdk.model.AnswerAudit audit) {
    return audit.knowledgeSettingsSnapshot();
  }
  static DatasetFileAppendResult appendSignature(DatasetsApi api, java.nio.file.Path file) {
    return api.appendFile("dataset", new DatasetFileUpload(file, "text/csv"), "stable-request");
  }
  static OrganizationChatSettings organizationSignature(OrganizationChatApi api) {
    var current = api.get(OrganizationChatFilter.empty().withWorkspaceId("workspace"));
    return api.update(OrganizationChatSettingsInput.empty().clearDefaultAgentId()
        .withExpectedRevision(current.revision()));
  }
  public static void main(String[] args) {
    try (var client = KoinonClient.builder(URI.create("http://127.0.0.1:1/api/v1"))
        .bearerToken(() -> "fictional-consumer-token").build()) {
      if (client.organizationPeople("example") == null || client.organizationKnowledge("example") == null || client.organizationChat("example") == null || client.catalog("example") == null || client.profile() == null) throw new AssertionError();
      var value = ExactValues.decimal(new BigDecimal("12345678901234567890.00100"));
      if (!value.textValue().equals("12345678901234567890.00100")) throw new AssertionError();
      if (!RequestOptions.defaults().ifMatch("revision").headers().containsKey("If-Match")) throw new AssertionError();
    }
  }
}
""")
        subprocess.run(
            [
                "javac",
                "--release",
                "21",
                "-Xlint:all",
                "-Werror",
                "-cp",
                classpath,
                "-d",
                str(consumer),
                str(source),
            ],
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["java", "-cp", str(consumer) + os.pathsep + classpath, "HeadlessConsumer"],
            check=True,
            timeout=30,
        )
    print(
        "Installed Java JAR: external typed consumer, Java 21 bytecode and notices passed."
    )


if __name__ == "__main__":
    main()
