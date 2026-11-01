<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Evidence workflows

## Explain a policy

For “What does our current policy say about retention?”, discover the current scope, search for the requested policy, fetch the relevant sources, and explain the sections that support the answer. Cite source identifiers and dates returned by koinon. If sources disagree, state that conflict and distinguish the current policy from historical versions only when the evidence supports it.

## Investigate a metric

For “Why did this metric change?”, discover the relevant dataset and inspect its schema. Query the smallest useful read-only comparison within the live tool's limits. Fetch supporting documentation for the metric definition. Explain observed values separately from possible causes; a correlated change is not proof of causation.

## Review answer support

For “Is this answer backed by our knowledge?”, collect the source material that the answer claims to use, inspect the provenance where relevant, and request the available answer audit. Describe the returned audit findings, then identify the statements directly supported by inspected evidence and the statements still unverified. Do not turn an audit status into an independent correctness guarantee.

## Organize existing knowledge

For “Move the renewal collection into the operations project,” inspect the current catalog entry, parent, space and project. Use the dedicated move tool only if the requested destination is compatible with the current server policy. Pass the returned exact parent and timestamp. Explain a rejected cross-project or protected-root move; never fabricate ancestry or silently pick another destination.

For a rename or tag change, read the current public metadata, retain fields the user wants to keep, and submit the exact replacement map with the fetched timestamp. If another writer changed the entry, show the new state before another decision. A recoverable archive is separate from permanent deletion and from publishing an AI-written summary.

## Resolve a lost create response

If folder creation times out, report that it may already have committed. Do not issue the create request again as a retry. Inspect the authorized parent and compare the actual entries with the user's intended folder; a matching display name alone does not prove which operation created it. Ask for the next decision if the result remains ambiguous.
