<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# Knowledge performance probes

`corpus_metadata.py` measures the selected-source metadata stage with the real native repository, SQLite and RLM corpus builder. It does not call a model, read document content, pin immutable versions or authorize a product caller. Synthetic source rows are deliberately unversioned; this is not a product RLM acceptance test.

Each sample uses a separate process and in-memory database. Setup is outside elapsed and process CPU timing. Reported RSS is the process lifetime maximum, including imports and fixture setup; it must not be labeled per-stage memory. The fixture warms SQLite, and OS caches are uncontrolled. Samples verify exact selected membership, excluded scope/status rows, duplicate-filename preservation, 200-ID SQL batches and zero object reads.

From the repository root, install the locked native development environment and run:

```bash
uv sync --project packages/canon --locked --extra dev
PYTHONPATH=packages/canon/src:packages/structured/src \
  packages/canon/.venv/bin/python tools/performance/corpus_metadata.py \
  --sizes 100 1000 10000 --repeats 5 \
  --output /tmp/koinon-metadata-study/run.json
```

Use `--stored 50000 --sizes 100` to keep the selected scope fixed while growing the catalog. Use `--analyze` to update SQLite planner statistics before timing; otherwise the fixture has no collected statistics. Receipts include the first batch's query plan, captured outside the timed phase. This distinguishes query count from the database's chosen access path.

The default catalog contains twice the selected count plus three excluded rows. The probe limits fixture creation to 100,000 ordinary rows plus those three sentinels, and 20 repetitions. It uses a 180-second child deadline and refuses to overwrite receipts. These are local test guardrails, not product limits. It deletes no files or external databases.

Validation:

```bash
PYTHONPATH=tools/performance:packages/canon/src:packages/structured/src \
  packages/canon/.venv/bin/python -m unittest discover \
  -s tools/performance/tests -v
packages/canon/.venv/bin/ruff check --config packages/canon/pyproject.toml tools/performance
packages/canon/.venv/bin/pyright -p tools/performance \
  --pythonpath packages/canon/.venv/bin/python
```

The [performance study](../../docs/concepts/knowledge-performance-study.md) explains measured native-provider results, per-stage complexity, cost accounting and the separate full-installation qualification matrix. Generated receipts belong in an operator-owned evidence directory, not a release package or source commit.

## Office document extraction

`office_files.py` creates actual DOCX, XLSX, CSV and PPTX originals, then runs the native bounded document parser. It measures document reading, not structured dataset ingestion, uploads, worker queues, embeddings or chat. XLSX and CSV are deliberately exercised through the document parser; their SQL dataset path requires separate qualification.

```bash
PYTHONPATH=packages/canon/src:packages/structured/src \
  packages/canon/.venv/bin/python tools/performance/office_files.py \
  --output /tmp/koinon-office-study/run-1 --repeats 3
```

The output directory must not already exist. The probe preserves originals, individual receipts, diagnostic logs and a completion manifest containing hashes. It stops on the first failing sample, preserves its diagnostics and does not raise product resource limits. It deletes no files or databases. Restrict a run with `--formats docx pptx` when investigating one parser family.

The fixed matrix includes DOCX documents with 100, 1,000 and 4,000 paragraphs, PPTX presentations with 10, 100 and 500 slides, and XLSX/CSV files with 1,000, 10,000 and 50,000 four-column rows. These synthetic fixtures establish extraction behavior; they do not represent image-heavy slides, scanned documents, workbook formulas or arbitrary customer files. The local probe permits at most five repetitions and 512 MiB of stored fixtures.

Each sample starts a fresh parent process and the parser's actual child. Timing includes the native parsing call, child startup and cleanup; it excludes fixture generation, hashing and result verification. Receipts separate wall time, parent CPU seconds, completed-child CPU seconds and the child's reported peak RSS. They also record original, expanded and emitted text bytes, the unchanged parser policy and complete evidence-marker coverage. Reported peak RSS includes child imports and extraction up to the native measurement, before result serialization. It can exclude later output and cleanup peaks. OS caches and shared-host load are uncontrolled; do not infer production concurrency or p95 latency from three sequential samples.
