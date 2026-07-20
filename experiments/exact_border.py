"""Experiment 1: a genuinely partial algebraic border."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

from fedpath import (
    AttemptPlan,
    NoContract,
    PlannedStep,
    ResidueContract,
    compare,
    report,
)

OPS: dict[str, Callable[[int, int], int]] = {
    "add": lambda value, operand: value + operand,
    "sub": lambda value, operand: value - operand,
    "mul": lambda value, operand: value * operand,
}


def build_chain(depth: int, seed: int) -> list[tuple[str, int]]:
    rng = random.Random(seed)
    return [(rng.choice(tuple(OPS)), rng.randint(2, 9)) for _ in range(depth)]


def truth_trace(chain: Sequence[tuple[str, int]], start: int = 1) -> list[int]:
    values: list[int] = []
    value = start
    for operation, operand in chain:
        value = OPS[operation](value, operand)
        values.append(value)
    return values


def build_fault_plan(
    *,
    trials: int,
    depth: int,
    attempts: int,
    p: float,
    modulus: int,
    preserving_share: float,
    seed: int,
) -> AttemptPlan[int]:
    """Generate deltas before any policy runs.

    A nonzero fraction of corruptions preserve the residue and therefore cross
    the partial border undetected.
    """

    rng = random.Random(seed)
    detectable = [
        delta
        for delta in range(-3 * modulus, 3 * modulus + 1)
        if delta != 0 and delta % modulus != 0
    ]
    preserving = [-2 * modulus, -modulus, modulus, 2 * modulus]
    nested: list[list[list[int]]] = []
    for _ in range(trials):
        trial: list[list[int]] = []
        for _ in range(depth):
            step_attempts: list[int] = []
            for _ in range(attempts):
                if rng.random() >= p:
                    step_attempts.append(0)
                elif rng.random() < preserving_share:
                    step_attempts.append(rng.choice(preserving))
                else:
                    step_attempts.append(rng.choice(detectable))
            trial.append(step_attempts)
        nested.append(trial)
    return AttemptPlan.from_nested(nested)


def run_experiment(
    *,
    depth: int = 12,
    p: float = 0.06,
    modulus: int = 7,
    preserving_share: float = 0.25,
    trials: int = 5000,
    seed: int = 1,
    max_redo: int = 3,
) -> dict[str, dict[str, float]]:
    chain = build_chain(depth, seed)
    truth = truth_trace(chain)
    target = truth[-1]
    plan = build_fault_plan(
        trials=trials,
        depth=depth,
        attempts=max_redo + 1,
        p=p,
        modulus=modulus,
        preserving_share=preserving_share,
        seed=seed * 100_003 + 17,
    )

    def steps_factory(trial_index: int):
        steps = []
        for step_index, (operation, operand) in enumerate(chain):
            tokens = plan.attempts(trial_index, step_index)

            def apply(incoming, delta, operation=operation, operand=operand):
                base = 1 if incoming is None else incoming
                return OPS[operation](base, operand) + delta

            steps.append(PlannedStep(tokens, apply))
        return steps

    def is_step_correct(step_index: int, incoming: int | None, candidate: int) -> bool:
        operation, operand = chain[step_index]
        base = 1 if incoming is None else incoming
        return candidate == OPS[operation](base, operand)

    contracts = {
        "none": NoContract(),
        "residue": ResidueContract(modulus, lambda index: truth[index]),
    }
    return compare(
        steps_factory,
        contracts,
        lambda value: value == target,
        is_step_correct=is_step_correct,
        trials=trials,
        keys=list(range(depth)),
        max_redo=max_redo,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--p", type=float, default=0.06)
    parser.add_argument("--modulus", type=int, default=7)
    parser.add_argument("--preserving-share", type=float, default=0.25)
    parser.add_argument("--trials", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-redo", type=int, default=3)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    results = run_experiment(
        depth=args.depth,
        p=args.p,
        modulus=args.modulus,
        preserving_share=args.preserving_share,
        trials=args.trials,
        seed=args.seed,
        max_redo=args.max_redo,
    )
    print(
        "exact algebraic border | "
        f"depth={args.depth} p={args.p} mod={args.modulus} "
        f"residue-preserving-share={args.preserving_share} | "
        f"{args.trials} paired trials\n"
    )
    print(report(results))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
