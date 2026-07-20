"""Core execution primitives for fail-closed reasoning paths."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any, Callable

Step = Callable[[Any], Any]
GoalOracle = Callable[[Any], bool]
StepOracle = Callable[[int, Any, Any], bool]


class Contract:
    """A cheap check applied before a step output may cross a boundary."""

    def check(self, key: Any, value: Any) -> bool:
        raise NotImplementedError


class NoContract(Contract):
    """Monolithic baseline: every value is accepted."""

    def check(self, key: Any, value: Any) -> bool:
        return True


@dataclass(frozen=True)
class StepTrace:
    """Recorded execution details for one path step."""

    step_index: int
    key: Any
    incoming: Any
    attempts: tuple[Any, ...]
    accepted_value: Any


@dataclass
class PathResult:
    """Outcome and directly measured execution costs for one path run."""

    value: Any
    correct: bool
    accepted: bool = True
    step_evaluations: int = 0
    contract_evaluations: int = 0
    rejections: int = 0
    false_rejections: int = 0
    exhausted_step: int | None = None
    trace: list[StepTrace] = field(default_factory=list)

    @property
    def work(self) -> int:
        """Backward-compatible alias for step_evaluations."""

        return self.step_evaluations


class BorderExhausted(RuntimeError):
    """Raised when no candidate passes a border within the retry budget."""

    def __init__(
        self,
        *,
        step_index: int,
        key: Any,
        attempts: int,
        last_value: Any,
        partial_result: PathResult,
    ) -> None:
        self.step_index = step_index
        self.key = key
        self.attempts = attempts
        self.last_value = last_value
        self.partial_result = partial_result
        super().__init__(
            f"border exhausted at step {step_index} after {attempts} attempts"
        )


def run_path(
    steps: Sequence[Step],
    contract: Contract,
    is_goal_correct: GoalOracle,
    *,
    is_step_correct: StepOracle | None = None,
    keys: Sequence[Any] | None = None,
    max_redo: int = 3,
    keep_trace: bool = False,
    on_exhausted: str = "raise",
) -> PathResult:
    """Execute a path and never let a rejected value reach a later step.

    ``max_redo`` is the number of retries after the initial attempt. With the
    default of 3, a step can be evaluated at most 4 times.

    ``is_goal_correct`` and ``is_step_correct`` are scoring oracles only. They
    are never consulted by the contract. The step-level oracle is required for
    meaningful false-rejection counts.

    ``on_exhausted`` may be ``"raise"`` (default) or ``"return"``. Both modes
    fail closed: no downstream step is called after exhaustion.
    """

    if max_redo < 0:
        raise ValueError("max_redo must be non-negative")
    if on_exhausted not in {"raise", "return"}:
        raise ValueError("on_exhausted must be 'raise' or 'return'")
    if keys is not None and len(keys) != len(steps):
        raise ValueError("keys must have the same length as steps")

    value: Any = None
    step_evaluations = 0
    contract_evaluations = 0
    rejections = 0
    false_rejections = 0
    traces: list[StepTrace] = []

    for step_index, step in enumerate(steps):
        key = keys[step_index] if keys is not None else step_index
        incoming = value
        attempted_values: list[Any] = []

        for attempt_index in range(max_redo + 1):
            candidate = step(incoming)
            attempted_values.append(candidate)
            step_evaluations += 1

            accepted = contract.check(key, candidate)
            contract_evaluations += 1
            if accepted:
                value = candidate
                if keep_trace:
                    traces.append(
                        StepTrace(
                            step_index=step_index,
                            key=key,
                            incoming=incoming,
                            attempts=tuple(attempted_values),
                            accepted_value=candidate,
                        )
                    )
                break

            rejections += 1
            if is_step_correct is not None and is_step_correct(
                step_index, incoming, candidate
            ):
                false_rejections += 1

            if attempt_index == max_redo:
                result = PathResult(
                    value=incoming,
                    correct=False,
                    accepted=False,
                    step_evaluations=step_evaluations,
                    contract_evaluations=contract_evaluations,
                    rejections=rejections,
                    false_rejections=false_rejections,
                    exhausted_step=step_index,
                    trace=traces,
                )
                if on_exhausted == "return":
                    return result
                raise BorderExhausted(
                    step_index=step_index,
                    key=key,
                    attempts=max_redo + 1,
                    last_value=candidate,
                    partial_result=result,
                )

    return PathResult(
        value=value,
        correct=is_goal_correct(value),
        accepted=True,
        step_evaluations=step_evaluations,
        contract_evaluations=contract_evaluations,
        rejections=rejections,
        false_rejections=false_rejections,
        trace=traces,
    )


def wilson_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""

    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must be between 0 and trials")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")

    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = (
        z
        * ((p * (1 - p) / trials + z * z / (4 * trials * trials)) ** 0.5)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def compare(
    steps_factory: Callable[[int], Sequence[Step]],
    contracts: Mapping[str, Contract],
    is_goal_correct: GoalOracle,
    *,
    is_step_correct: StepOracle | None = None,
    trials: int = 200,
    keys: Sequence[Any] | None = None,
    max_redo: int = 3,
    confidence: float = 0.95,
) -> dict[str, dict[str, float]]:
    """Compare policies using trial-indexed, reproducible step factories.

    The factory is called once per policy with the same ``trial_index``. It
    must derive all exogenous randomness only from that index and immutable
    configuration. Experiments in this repository additionally use
    attempt-indexed fault plans, so retries cannot shift later faults.
    """

    if trials <= 0:
        raise ValueError("trials must be positive")

    totals: dict[str, dict[str, float]] = {
        name: {
            "correct": 0.0,
            "accepted": 0.0,
            "step_evaluations": 0.0,
            "contract_evaluations": 0.0,
            "rejections": 0.0,
            "false_rejections": 0.0,
            "exhaustions": 0.0,
        }
        for name in contracts
    }

    # Trials are the outer loop so every policy is evaluated against the same
    # indexed case before moving to the next case.
    for trial_index in range(trials):
        for name, contract in contracts.items():
            result = run_path(
                steps_factory(trial_index),
                contract,
                is_goal_correct,
                is_step_correct=is_step_correct,
                keys=keys,
                max_redo=max_redo,
                on_exhausted="return",
            )
            bucket = totals[name]
            bucket["correct"] += float(result.correct)
            bucket["accepted"] += float(result.accepted)
            bucket["step_evaluations"] += result.step_evaluations
            bucket["contract_evaluations"] += result.contract_evaluations
            bucket["rejections"] += result.rejections
            bucket["false_rejections"] += result.false_rejections
            bucket["exhaustions"] += float(not result.accepted)

    output: dict[str, dict[str, float]] = {}
    for name, bucket in totals.items():
        correct = int(bucket["correct"])
        accepted = int(bucket["accepted"])
        correct_low, correct_high = wilson_interval(correct, trials, confidence)
        accepted_low, accepted_high = wilson_interval(accepted, trials, confidence)
        output[name] = {
            "trials": float(trials),
            "correct_pct": 100.0 * correct / trials,
            "correct_ci_low_pct": 100.0 * correct_low,
            "correct_ci_high_pct": 100.0 * correct_high,
            "accepted_pct": 100.0 * accepted / trials,
            "accepted_ci_low_pct": 100.0 * accepted_low,
            "accepted_ci_high_pct": 100.0 * accepted_high,
            "step_evaluations": bucket["step_evaluations"] / trials,
            "contract_evaluations": bucket["contract_evaluations"] / trials,
            "rejections": bucket["rejections"] / trials,
            "false_rejections": bucket["false_rejections"] / trials,
            "exhaustions": bucket["exhaustions"] / trials,
        }
    return output


def report(results: Mapping[str, Mapping[str, float]]) -> str:
    """Render comparison results with confidence intervals and real metric names."""

    lines = [
        f"{'border':>14} {'goal correct (95% CI)':>28} "
        f"{'accepted':>10} {'step evals':>11} {'rejects':>9} "
        f"{'false rej':>10} {'exhaust':>8}"
    ]
    for name, row in results.items():
        interval = (
            f"{row['correct_pct']:.1f}% "
            f"[{row['correct_ci_low_pct']:.1f}, {row['correct_ci_high_pct']:.1f}]"
        )
        lines.append(
            f"{name:>14} {interval:>28} {row['accepted_pct']:>9.1f}% "
            f"{row['step_evaluations']:>11.2f} {row['rejections']:>9.2f} "
            f"{row['false_rejections']:>10.2f} {row['exhaustions']:>8.3f}"
        )
    return "\n".join(lines)
