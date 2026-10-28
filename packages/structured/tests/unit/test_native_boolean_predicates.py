# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from flyquery.core.services.execution.ast_classifier import AstClassifier
from flyquery.core.services.execution.scope_guard import ScopeGuard


def test_pure_boolean_predicates_remain_registered_read_only_sql():
    classifier = AstClassifier()
    for sql in [
        "SELECT total FROM Forecast WHERE region='north' OR region='south'",
        "SELECT total FROM Forecast WHERE total>0 AND region='north'",
    ]:
        actual = classifier.classify(sql)
        assert not actual.unsupported_sql
        ScopeGuard().check(
            classification=actual,
            scopes={"flyquery.query:read"},
            table_kinds_by_name={"Forecast": "UPLOADED"},
            dataset_allowlist={"owned"},
            dataset_of_table={"Forecast": "owned"},
        )


def test_boolean_expression_does_not_hide_a_non_pure_function():
    classifier = AstClassifier()
    assert classifier.classify(
        "SELECT total FROM Forecast WHERE region='north' OR unknown_function(total)>0"
    ).unsupported_sql
