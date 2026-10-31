// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.net.URI;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class TutorialMain {
    private TutorialMain() {}

    private static String required(String name) {
        var value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Set " + name);
        }
        return value;
    }

    public static void main(String[] args) {
        if (args.length != 1) {
            throw new IllegalArgumentException("Choose context, history, threads or people");
        }
        try (var client = KoinonClient.builder(URI.create(required("KOINON_API_URL")))
                .bearerToken(() -> required("KOINON_TOKEN")).build()) {
            var tenant = required("KOINON_TENANT_ID");
            switch (args[0]) {
                case "context" -> {
                    var context = client.platform().context();
                    System.out.println("Available organizations: " + context.tenants().size());
                }
                case "history" -> {
                    var versions = JavaHistory.documentVersions(client, tenant,
                        required("KOINON_DOCUMENT_ID"), 1);
                    for (var version : versions.items()) {
                        System.out.println(version.sourceVersionId() + " " + version.sha256());
                    }
                }
                case "threads" -> {
                    var threads = client.chat(tenant).threads(
                        ThreadFilter.empty().withPage(1).withPageSize(25));
                    for (var thread : threads.items()) {
                        System.out.println(thread.id() + " " + thread.title());
                    }
                }
                case "people" -> {
                    var person = client.organizationPeople(tenant).me();
                    System.out.println(person.id() + " " + person.jobTitle());
                }
                default -> throw new IllegalArgumentException("Unknown tutorial command");
            }
        }
    }
}
