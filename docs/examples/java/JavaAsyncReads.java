// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.time.Duration;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import org.fireflyframework.koinon.sdk.ApiException;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.CatalogEntry;
import org.fireflyframework.koinon.sdk.model.CatalogFilter;
import org.fireflyframework.koinon.sdk.model.Page;

public final class JavaAsyncReads {
    public static CompletableFuture<Page<CatalogEntry>> load(KoinonClient client,
            String tenant, String workspace) {
        var pending = client.catalog(tenant).listAsync(CatalogFilter.empty()
            .withWorkspaceId(workspace).withPage(1).withPageSize(25),
            RequestOptions.defaults().timeout(Duration.ofSeconds(45)));
        pending.whenComplete((page, error) -> {
            if (error == null) System.out.println("Loaded " + page.items().size() + " entries");
            else report(error);
        });
        return pending;
    }

    private static void report(Throwable error) {
        Throwable cause = error;
        while (cause instanceof CompletionException && cause.getCause() != null) {
            cause = cause.getCause();
        }
        if (cause instanceof ApiException problem) {
            System.err.println("HTTP " + problem.status() + " code=" + problem.code()
                + " request=" + problem.requestId());
        } else {
            System.err.println("Request failed: " + cause.getClass().getSimpleName());
        }
    }
}
