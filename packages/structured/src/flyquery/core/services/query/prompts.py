# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Prompt rendering for the structured query stages."""

from typing import Any

from flyquery.core.services.query import value_anchoring


def _render_grounding_prompt(
    *,
    question: str,
    bundle: dict,
    starting_point_sql: str | None,
) -> str:
    """Pack the retrieved schema KB into a Claude-readable grounding prompt."""

    out: list[str] = []
    out.append("# User question")
    out.append(question.strip())
    out.append("")

    if starting_point_sql:
        out.append("# Prior turn (drill-down starting point)")
        out.append("```sql")
        out.append(starting_point_sql.strip())
        out.append("```")
        out.append("")

    # 1. The "Complete dataset catalogue" lists EVERY table in the dataset.
    #    Ground-truth inventory the LLM must pick from; prevents
    #    hallucination of plausible-but-nonexistent tables like
    #    ``balance_sheet`` / ``income_statement``.
    inventory = bundle.get("schema_inventory", []) or []
    inv_tables = [h for h in inventory if (getattr(h, "metadata", {}) or {}).get("kind") == "TABLE"]
    if inv_tables:
        out.append(f"# Complete dataset catalogue ({len(inv_tables)} tables)")
        out.append(
            "These are the ONLY tables available. Use exactly these qualified "
            "names. Never invent table names like `balance_sheet`, "
            "`income_statement`, or `financials.*` -- if the user asks about "
            "assets, find the matching table below (it may be named in "
            "another language: Spanish `Activos` for English `Assets`, "
            "`Cuenta de Pérdidas y Ganancias` for `Profit & Loss`)."
        )
        for h in inv_tables:
            md = getattr(h, "metadata", None) or {}
            qn = md.get("qualified_name") or "?"
            text = getattr(h, "text", "") or ""
            text = text.replace("\n", " ").strip()
            if len(text) > 160:
                text = text[:157] + "…"
            out.append(f"- `{qn}` :: {text}")
        out.append("")

    # 2. The "Top-ranked columns" section -- only column-level hits
    #    from the hybrid retriever, ranked. Helps the LLM zero in on
    #    the right columns once it has picked a table.
    schema_hits = bundle.get("schema_objects", []) or []
    column_hits = [h for h in schema_hits if (getattr(h, "metadata", {}) or {}).get("kind") != "TABLE"]
    if column_hits:
        out.append(f"# Top-ranked column matches ({len(column_hits)})")
        out.append(
            "Most relevant column-level matches for this question, ranked by "
            "BM25 + vector retrieval. Prefer these when writing the SQL. "
            "Column names that look like dates (e.g. `2024-12-31`) are "
            "legitimate XLSX column names and must be quoted."
        )
        for h in column_hits[:200]:
            md = getattr(h, "metadata", None) or {}
            qn = md.get("qualified_name") or "?"
            text = getattr(h, "text", "") or ""
            text = text.replace("\n", " ").strip()
            if len(text) > 200:
                text = text[:197] + "…"
            out.append(f"- `{qn}` :: {text}")
        out.append("")

    examples = bundle.get("examples", []) or []
    if examples:
        out.append(f"# Approved Q→SQL examples ({len(examples)})")
        for h in examples[:5]:
            md = getattr(h, "metadata", None) or {}
            q = md.get("question", "")
            sql = md.get("sql", "")
            out.append(f"- Q: {q}\n  SQL: `{sql}`")
        out.append("")

    metrics = bundle.get("metrics", []) or []
    if metrics:
        out.append(f"# Published semantic metrics ({len(metrics)})")
        for h in metrics[:5]:
            md = getattr(h, "metadata", None) or {}
            out.append(f"- `{md.get('name')}` -- {md.get('description', '')}")
        out.append("")

    glossary = bundle.get("glossary", []) or []
    if glossary:
        out.append(f"# Glossary terms ({len(glossary)})")
        for h in glossary[:10]:
            md = getattr(h, "metadata", None) or {}
            line = f"- **{md.get('term')}**: {md.get('definition', '')}"
            related = md.get("related_metrics") or []
            if related:
                # A glossary term that maps to a published metric is a strong
                # signal to take the SEMANTIC_LAYER path using that metric.
                line += f" (related metrics: {', '.join(related)})"
            out.append(line)
        out.append("")

    relations = bundle.get("relations", []) or []
    if relations:
        out.append(f"# Approved relations / join hints ({len(relations)})")
        for h in relations[:10]:
            md = getattr(h, "metadata", None) or {}
            out.append(
                f"- {md.get('from_table')}.{md.get('from_column')} "
                f"→ {md.get('to_table')}.{md.get('to_column')} "
                f"(confidence={md.get('confidence')})"
            )
        out.append("")

    out.append("# Task")
    out.append(
        "Produce the GroundedContext for this question. Pick the MINIMAL set of "
        "tables, columns, and joins. If a published metric covers the question, "
        "set path=SEMANTIC_LAYER. Otherwise path=SYNTHESIS. Set confidence ∈ [0,1] "
        "and only populate `missing_info` when confidence is below 0.55."
    )
    return "\n".join(out)


def _lookup_col(qn: str, cat_by_qn: dict) -> dict | None:
    if qn in cat_by_qn:
        return cat_by_qn[qn]
    # tolerate grounding returning a shorter/unqualified column name
    tail = qn.rsplit(".", 1)[-1].lower()
    for k, v in cat_by_qn.items():
        if k.rsplit(".", 1)[-1].lower() == tail:
            return v
    return None


def _render_generation_prompt(
    question: str,
    grounded: Any,
    starting_point_sql: str | None,
    *,
    schema_inventory: list[Any] | None = None,
    col_catalog: list[dict] | None = None,
    resolved_entities: list[dict] | None = None,
    resolved_groups: list[dict] | None = None,
    hierarchy_intent: bool = False,
    examples: list[Any] | None = None,
    n_candidates: int = 3,
    max_columns: int = 80,
    char_budget: int = 320,
) -> str:
    """Pack the grounded context + the per-column VALUE CATALOGUE into a prompt.

    The generation prompt now shows, for each in-scope column, its data_type,
    semantic role (measure/dimension/time), and the actual distinct VALUES (or
    numeric range) the column holds -- so the SQL writer copies real filter
    literals instead of inventing them. Question entities that were located in
    the data are listed explicitly. All sourced from the dataset's own
    ingest-time profiling; nothing is hardcoded.
    """
    from collections import defaultdict

    cat_by_qn = {c["qualified_name"]: c for c in (col_catalog or [])}
    cols_by_table: dict[str, list[dict]] = defaultdict(list)
    for c in col_catalog or []:
        cols_by_table[c["qualified_name"].rsplit(".", 1)[0]].append(c)

    out: list[str] = []
    out.append("# User question")
    out.append(question.strip())
    out.append("")

    if starting_point_sql:
        out.append("# Prior turn SQL (build a delta on top of this when possible)")
        out.append("```sql")
        out.append(starting_point_sql.strip())
        out.append("```")
        out.append("")

    if resolved_entities:
        out.append("# Resolved entities (literals located in the data)")
        out.append(
            "These exact question literals were FOUND as stored values. Filter on "
            "the stated column with the stated value verbatim. When a literal was "
            "found in MORE THAN ONE column, the number of rows it matches is shown:"
        )
        for e in resolved_entities[:24]:
            cnt = e.get("match_count")
            tag = ""
            if cnt is not None:
                role = "repeats → grouping/parent key" if cnt > 1 else "appears once → identity"
                tag = f" — matches {cnt} row(s), {role}"
            out.append(f"- '{e['literal']}' → column `{e['column']}` (stored value: {e['value']!r}){tag}")
        if hierarchy_intent:
            out.append(
                "NOTE: this is a hierarchy / team / reporting question. Filter the column where the "
                "entity REPEATS across rows (the parent/manager key), NOT where it appears once (its "
                "own identity row). Prefer the table with the MOST matching rows over a stale one."
            )
            top = max(
                (e for e in resolved_entities if (e.get("match_count") or 0) > 1),
                key=lambda e: e.get("match_count") or 0,
                default=None,
            )
            if top is not None:
                out.append(
                    f"  >> Best binding: filter on `{top['column']}` (the entity matches "
                    f"{top['match_count']} rows there) — query THAT column in THAT table; ignore "
                    f"tables/columns where the name appears only 0–1 times."
                )
        out.append("")

    if resolved_groups:
        out.append("# Resolved value groups (a term that spans several stored values)")
        out.append(
            "Each question term below is an umbrella over MULTIPLE values of one column — it "
            "means the WHOLE set, never a subset:"
        )
        for g in resolved_groups[:12]:
            col = g["column"].rsplit(".", 1)[-1]
            vlist = ", ".join(repr(v) for v in g["values"])
            if g.get("truncated"):
                out.append(
                    f"- '{g['literal']}' spans column `{col}` (the catalogued list is INCOMPLETE) — "
                    f"use `{col} LIKE '{g['literal']}%'` to capture every member."
                )
            else:
                out.append(
                    f"- '{g['literal']}' spans these values in `{col}`: [{vlist}] — "
                    f"use IN(all of them) or `{col} LIKE '{g['literal']}%'`; never a subset."
                )
        out.append("")

    inv = schema_inventory or []
    inv_tables = [h for h in inv if (getattr(h, "metadata", {}) or {}).get("kind") == "TABLE"]
    if inv_tables:
        out.append(f"# Complete dataset catalogue ({len(inv_tables)} tables)")
        out.append(
            "Every table in this dataset. The SQL you generate MUST reference "
            "tables from this list only -- never invent table names like "
            "`balance_sheet`, `income_statement`, or `financials.*`."
        )
        for h in inv_tables:
            md = getattr(h, "metadata", None) or {}
            qn = md.get("qualified_name") or "?"
            text = getattr(h, "text", "") or ""
            text = text.replace("\n", " ").strip()
            if len(text) > 160:
                text = text[:157] + "…"
            out.append(f"- `{qn}` :: {text}")
        out.append("")

    g_path = getattr(grounded, "path", None)
    g_tables = getattr(grounded, "tables", []) or []
    g_columns = getattr(grounded, "columns", []) or []
    g_joins = getattr(grounded, "joins", []) or []

    out.append(f"# Grounded context (path = {g_path})")
    if g_tables:
        out.append("## Tables in scope")
        for t in g_tables:
            out.append(f"- `{getattr(t, 'table_qualified_name', t)}`")
        out.append("")

    # Full, value-anchored column listing for every in-scope table. This both
    # raises recall (the right column may have ranked below top-12) and gives
    # the SQL writer the real literal vocabulary for each column.
    rendered = 0
    table_qns = [getattr(t, "table_qualified_name", str(t)) for t in g_tables]
    if not table_qns:
        # No grounded tables: fall back to every table that has columns.
        table_qns = list(cols_by_table.keys())
    if table_qns:
        out.append("## Columns with values (use these literals verbatim)")
        for tqn in table_qns:
            cols = cols_by_table.get(tqn) or []
            if not cols:
                # match by table-name tail when grounding used a short qn
                tail = tqn.rsplit(".", 1)[-1].lower()
                for k, v in cols_by_table.items():
                    if k.rsplit(".", 1)[-1].lower() == tail:
                        cols = v
                        break
            if not cols:
                continue
            out.append(f"### `{tqn}`")
            for c in cols:
                if rendered >= max_columns:
                    out.append("- … (column list truncated)")
                    break
                out.append(
                    "- "
                    + value_anchoring.render_catalog_from_meta(
                        c["qualified_name"], c, char_budget=char_budget
                    )
                )
                rendered += 1
            out.append("")
            if rendered >= max_columns:
                break
    elif g_columns:
        out.append("## Columns in scope")
        for c in g_columns:
            qn = getattr(c, "column_qualified_name", str(c))
            meta = _lookup_col(qn, cat_by_qn)
            if meta:
                out.append("- " + value_anchoring.render_catalog_from_meta(qn, meta, char_budget=char_budget))
            else:
                out.append(f"- `{qn}`")
        out.append("")

    if g_joins:
        out.append("## Approved joins")
        for j in g_joins:
            out.append(
                f"- `{getattr(j, 'from_table', '')}.{getattr(j, 'from_column', '')}` "
                f"= `{getattr(j, 'to_table', '')}.{getattr(j, 'to_column', '')}` "
                f"({getattr(j, 'relationship', 'inner')} join)"
            )
        out.append("")

    if examples:
        out.append(f"# Worked examples (approved Q→SQL, {len(examples)})")
        for h in examples[:5]:
            md = getattr(h, "metadata", None) or {}
            out.append(f"- Q: {md.get('question', '')}\n  SQL: `{md.get('generated_sql', '')}`")
        out.append("")

    out.append("# Task")
    out.append(
        f"Generate {n_candidates} candidate DuckDB SQL queries that answer the question, "
        "ordered by confidence (highest first). Each candidate must:\n"
        "- Use only the tables and columns listed above. Reference each table by its "
        "**unqualified name** (the last segment of the qualified name).\n"
        "- For every WHERE / GROUP BY / JOIN literal, COPY a value shown in the "
        "'values:' list of that column VERBATIM (exact case + spelling). Do NOT invent "
        "or translate filter literals. If the question's entity matches a value under a "
        "DIFFERENT column than you expected, filter on the column that actually holds it "
        "(see 'Resolved entities').\n"
        "- For a year/period/time column whose values are strings (e.g. 'FY23'), filter "
        "with the STRING form shown -- never an integer like 2023, and never use a numeric "
        "measure column as the year axis.\n"
        "- Aggregate measure columns; filter/group on dimension/time columns.\n"
        "- NEVER emit a no-op query (e.g. `WHERE 1=0`, `SUM(CASE WHEN ... THEN 0 ELSE 0 END)`, "
        "or a constant SELECT). If you cannot map a needed filter to a real value, widen or "
        "omit that filter and lower your confidence rather than returning a placeholder.\n"
        '- Quote any column name that isn\'t a plain identifier (e.g. `"2024-12-31"`, '
        '`"P&L Line"`).\n'
        "- Be a SINGLE SELECT statement (no multi-statement; no DDL)."
    )
    return "\n".join(out)


def _render_critic_prompt(
    *,
    question: str,
    failing_sql: str,
    error_message: str,
    grounded: Any,
    schema_inventory: list[Any] | None = None,
    value_hints: list[str] | None = None,
) -> str:
    out: list[str] = []
    out.append("# User question")
    out.append(question.strip())
    out.append("")
    out.append("# Previous SQL (needs repair)")
    out.append("```sql")
    out.append(failing_sql.strip())
    out.append("```")
    out.append("")
    out.append("# Problem")
    out.append(error_message.strip())
    out.append("")

    # The actual stored values of the columns the failing query filtered on --
    # so the critic replaces wrong literals with real ones instead of guessing
    # again (this is what fixes the silent 0-row failures).
    if value_hints:
        out.append("# Column value catalogue (verify EVERY filter literal against these)")
        for line in value_hints:
            out.append(f"- {line}")
        out.append("")

    # Full dataset catalogue -- the critic's most common failure mode
    # is rewriting one hallucinated table name into another (e.g.
    # ``balance_sheet`` -> ``financials.balance_sheet`` rather than
    # picking the real ``IVI_MALAGA_SL__Activos``). Showing every real
    # table by qualified_name + column fingerprint forces the critic
    # to pick from the catalogue.
    inv = schema_inventory or []
    inv_tables = [h for h in inv if (getattr(h, "metadata", {}) or {}).get("kind") == "TABLE"]
    if inv_tables:
        out.append(f"# Complete dataset catalogue ({len(inv_tables)} tables)")
        out.append(
            "ONLY these tables exist. If the failing SQL referenced anything "
            "else, that's the bug -- pick the right one from this list. Table "
            "names may be in any language (Spanish `Activos` = Assets, "
            "`Cuenta de Pérdidas y Ganancias` = Profit & Loss)."
        )
        for h in inv_tables:
            md = getattr(h, "metadata", None) or {}
            qn = md.get("qualified_name") or "?"
            text = getattr(h, "text", "") or ""
            text = text.replace("\n", " ").strip()
            if len(text) > 160:
                text = text[:157] + "…"
            out.append(f"- `{qn}` :: {text}")
        out.append("")

    g_tables = getattr(grounded, "tables", []) or []
    g_columns = getattr(grounded, "columns", []) or []
    if g_tables or g_columns:
        out.append("# Grounded scope (preferred tables / columns)")
        for t in g_tables:
            out.append(f"- table: `{getattr(t, 'table_qualified_name', t)}`")
        for c in g_columns:
            out.append(f"- column: `{getattr(c, 'column_qualified_name', c)}`")
        out.append("")
    out.append("# Task")
    out.append(
        "Return a corrected SQL that resolves the execution error. Output a "
        "RefinedSql with a brief reasoning + a confidence in [0,1]. Pick "
        "tables ONLY from the catalogue above. Use unqualified table names "
        "(last segment only) and quote any non-identifier column names like "
        '`"2024-12-31"`.'
    )
    return "\n".join(out)


def _render_explainer_prompt(
    *,
    question: str,
    executed_sql: str,
    row_count: int,
    preview_rows: list[dict],
) -> str:
    out: list[str] = []
    out.append("# User question")
    out.append(question.strip())
    out.append("")
    out.append("# Executed SQL")
    out.append("```sql")
    out.append(executed_sql.strip())
    out.append("```")
    out.append("")
    out.append("# Result")
    out.append(f"row_count: {row_count}")
    if preview_rows:
        out.append(f"rows (first {min(len(preview_rows), 50)}):")
        for row in preview_rows[:50]:
            out.append(f"- {row}")
    out.append("")
    out.append("# Task")
    out.append(
        "Produce a ResultExplanation with a 1-3 sentence NL summary that directly "
        "answers the question using the rows above, and a chart_hint picked from "
        "{line, bar, table, pie, none}. Never invent numbers -- cite only what is "
        "in the preview."
    )
    return "\n".join(out)
