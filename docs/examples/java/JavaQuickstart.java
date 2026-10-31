// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.net.URI;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.Pages;
import org.fireflyframework.koinon.sdk.model.CatalogFilter;

public final class JavaQuickstart {
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Set " + name);
        }
        return value;
    }

    public static void main(String[] args) {
        try (var client = KoinonClient.builder(URI.create(required("KOINON_API_URL")))
                .bearerToken(() -> required("KOINON_TOKEN")).build()) {
            client.platform().context();
            String tenant = required("KOINON_TENANT_ID");
            var filter = CatalogFilter.empty()
                .withWorkspaceId(required("KOINON_WORKSPACE_ID"))
                .withKind("document").withPageSize(25).withSort("name").withOrder("asc");
            for (var entry : Pages.numbered(
                    page -> client.catalog(tenant).list(filter.withPage(page)), 1)) {
                System.out.println(entry.id() + " " + entry.name());
            }
        }
    }
}
