import pytest

from fedpath import AttemptPlan, PlannedStep


def test_planned_step_consumes_attempt_tokens_without_shared_rng():
    plan = AttemptPlan.from_nested([[[1, 2], [3, 4]]])
    step = PlannedStep(
        plan.attempts(0, 0),
        lambda incoming, token: (incoming or 0) + token,
    )
    assert step(None) == 1
    assert step(10) == 12
    with pytest.raises(RuntimeError):
        step(10)
