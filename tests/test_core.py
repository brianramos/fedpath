from __future__ import annotations

import pytest

from fedpath import BorderExhausted, Contract, NoContract, compare, run_path


class AlwaysReject(Contract):
    def check(self, key, value):
        return False


def test_retry_exhaustion_fails_closed_and_skips_downstream_step():
    calls = []

    def first(_):
        calls.append("first")
        return 7

    def downstream(value):
        calls.append(("downstream", value))
        return value + 1

    with pytest.raises(BorderExhausted) as error:
        run_path(
            [first, downstream],
            AlwaysReject(),
            lambda value: False,
            max_redo=2,
        )

    assert calls == ["first", "first", "first"]
    assert error.value.step_index == 0
    assert error.value.attempts == 3


def test_return_mode_is_also_fail_closed():
    downstream_calls = 0

    def downstream(value):
        nonlocal downstream_calls
        downstream_calls += 1
        return value

    result = run_path(
        [lambda _: 1, downstream],
        AlwaysReject(),
        lambda value: False,
        max_redo=0,
        on_exhausted="return",
    )

    assert not result.accepted
    assert result.exhausted_step == 0
    assert downstream_calls == 0


def test_false_rejection_uses_step_oracle_not_goal_oracle():
    attempts = iter([2, 3])

    class RejectTwo(Contract):
        def check(self, key, value):
            return value != 2

    result = run_path(
        [lambda _: next(attempts)],
        RejectTwo(),
        lambda value: value == 3,
        is_step_correct=lambda index, incoming, candidate: candidate == 2,
        max_redo=1,
    )

    assert result.correct
    assert result.false_rejections == 1
    assert result.rejections == 1


def test_compare_reuses_trial_indices_for_every_policy():
    calls = []

    def factory(trial_index):
        calls.append(trial_index)
        return [lambda _: trial_index]

    results = compare(
        factory,
        {"a": NoContract(), "b": NoContract()},
        lambda value: value >= 0,
        trials=3,
    )

    assert calls == [0, 0, 1, 1, 2, 2]
    assert results["a"]["correct_pct"] == 100.0
