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
