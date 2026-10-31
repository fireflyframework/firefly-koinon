# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The model must receive the bounded native expression value it computed."""

import pytest

from flycanon.core.services.query.rlm.sandbox.monty_executor import ExecutionTreeBudget, MontyExecutor
from flycanon.core.services.query.rlm.session import RLMSession


@pytest.mark.parametrize(("code", "expected"), [
    ("['published-key']", '["published-key"]'),
    ("'The threshold is 47.'", '"The threshold is 47."'),
    ("0", '0'),
    ("False", 'false'),
    ("[]", '[]'),
    ("print('visible'); 2", 'visible\n2'),
    ("print('visible')", 'visible\n'),
    ("x = 1", '(no output)'),
])
def test_monty_observation_preserves_stdout_and_the_last_expression(code, expected):
    runner = MontyExecutor(functions={}, authorize=lambda: None, tree=ExecutionTreeBudget(1, 0),
                           max_iters=1, timeout=2)
    runner.start()
    try:
        feed = runner.run_block(code)
        assert feed.result.success
        observation, final = RLMSession(object())._monty_result(feed, runner)
        assert observation == expected
        assert final is None
    finally:
        runner.close()
