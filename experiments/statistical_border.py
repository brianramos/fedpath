"""Experiment 2: corpus support under novel and in-vocabulary faults."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from fedpath import (
    AttemptPlan,
    Contract,
    NoContract,
    PlannedStep,
    SurpriseContract,
    aggregate_document_frequencies,
    compare,
    local_document_frequency,
    report,
)


@dataclass(frozen=True)
class ClaimAttempt:
    term: str
    kind: str  # clean, novel, or decoy


class OracleContract(Contract):
    """Upper bound: validates each positional claim against its allowed set."""

    def __init__(self, valid_terms_by_step: Sequence[set[str]]):
        self.valid_terms_by_step = valid_terms_by_step

    def check(self, key: int, value: Sequence[str]) -> bool:
        return len(value) == key + 1 and all(
            term in self.valid_terms_by_step[index] for index, term in enumerate(value)
        )


def build_domain(
    *,
    n_terms: int,
    n_domains: int,
    docs_per_domain: int,
    seed: int,
) -> tuple[list[str], list[float], list[list[set[str]]]]:
    rng = random.Random(seed)
    terms = [f"t{index}" for index in range(n_terms)]
    weights = [1.0 / (index + 1) ** 1.1 for index in range(n_terms)]
    corpora: list[list[set[str]]] = []
    for _ in range(n_domains):
        documents: list[set[str]] = []
        for _ in range(docs_per_domain):
            documents.append(
                set(rng.choices(terms, weights=weights, k=rng.randint(3, 8)))
            )
        corpora.append(documents)
    return terms, weights, corpora


def build_valid_sets(
    terms: Sequence[str], weights: Sequence[float], depth: int, seed: int
) -> list[set[str]]:
    del weights  # validity is independent of corpus popularity
    if len(terms) < 12:
        raise ValueError("the statistical experiment needs at least 12 terms")

    rng = random.Random(seed)
    split = max(6, len(terms) // 4)
    common_pool = list(terms[:split])
    rare_pool = list(terms[split:])
    valid_sets: list[set[str]] = []
    for _ in range(depth):
        # Every step has both common and rare-but-real valid realizations.
        # Retries may choose another valid realization, so corpus sparsity
        # causes measurable false rejection and occasional safe exhaustion.
        common = rng.sample(common_pool, k=min(6, len(common_pool)))
        rare = rng.sample(rare_pool, k=min(6, len(rare_pool)))
        valid_sets.append(set(common + rare))
    return valid_sets


def weighted_choice_from_subset(
    rng: random.Random,
    subset: Iterable[str],
    term_to_weight: dict[str, float],
) -> str:
    values = sorted(subset)
    selected = rng.choices(
        values, weights=[term_to_weight[value] for value in values], k=1
    )
    return selected[0]


def build_fault_plan(
    *,
    trials: int,
    depth: int,
    attempts: int,
    p: float,
    decoy_share: float,
    terms: Sequence[str],
    weights: Sequence[float],
    valid_terms_by_step: Sequence[set[str]],
    seed: int,
) -> AttemptPlan[ClaimAttempt]:
    rng = random.Random(seed)
    term_to_weight = dict(zip(terms, weights))
    nested: list[list[list[ClaimAttempt]]] = []
    real = set(terms)

    for trial_index in range(trials):
        trial: list[list[ClaimAttempt]] = []
        for step_index in range(depth):
            valid = valid_terms_by_step[step_index]
            invalid_real = real - valid
            step_attempts: list[ClaimAttempt] = []
            for attempt_index in range(attempts):
                if rng.random() >= p:
                    term = rng.choice(sorted(valid))
                    step_attempts.append(ClaimAttempt(term, "clean"))
                elif rng.random() < decoy_share:
                    # A real, often common, but contextually invalid term.
                    term = weighted_choice_from_subset(
                        rng, invalid_real, term_to_weight
                    )
                    step_attempts.append(ClaimAttempt(term, "decoy"))
                else:
                    step_attempts.append(
                        ClaimAttempt(
                            f"x{trial_index}_{step_index}_{attempt_index}", "novel"
                        )
                    )
            trial.append(step_attempts)
        nested.append(trial)
    return AttemptPlan.from_nested(nested)


def run_config(
    *,
    n_terms: int = 400,
    n_domains: int = 6,
    docs: int = 120,
    depth: int = 10,
    p: float = 0.08,
    decoy_share: float = 0.35,
    threshold: int = 1,
    trials: int = 5000,
    seed: int = 1,
    max_redo: int = 3,
) -> tuple[int, dict[str, dict[str, float]]]:
    terms, weights, corpora = build_domain(
        n_terms=n_terms,
        n_domains=n_domains,
        docs_per_domain=docs,
        seed=seed,
    )
    local_maps = [local_document_frequency(corpus) for corpus in corpora]
    doc_freq = aggregate_document_frequencies(local_maps)
    coverage = sum(1 for term in terms if doc_freq.get(term, 0) > 0)
    valid_terms_by_step = build_valid_sets(terms, weights, depth, seed * 31 + 7)
    plan = build_fault_plan(
        trials=trials,
        depth=depth,
        attempts=max_redo + 1,
        p=p,
        decoy_share=decoy_share,
        terms=terms,
        weights=weights,
        valid_terms_by_step=valid_terms_by_step,
        seed=seed * 100_019 + docs,
    )

    def steps_factory(trial_index: int):
        steps = []
        for step_index in range(depth):
            tokens = plan.attempts(trial_index, step_index)

            def apply(incoming, attempt: ClaimAttempt):
                prefix = () if incoming is None else tuple(incoming)
                return prefix + (attempt.term,)

            steps.append(PlannedStep(tokens, apply))
        return steps

    def is_goal_correct(value: Sequence[str] | None) -> bool:
        return (
            value is not None
            and len(value) == depth
            and all(
                term in valid_terms_by_step[index] for index, term in enumerate(value)
            )
        )

    def is_step_correct(
        step_index: int,
        incoming: Sequence[str] | None,
        candidate: Sequence[str],
    ) -> bool:
        prefix = () if incoming is None else tuple(incoming)
        return (
            tuple(candidate[:-1]) == prefix
            and len(candidate) == len(prefix) + 1
            and candidate[-1] in valid_terms_by_step[step_index]
        )

    contracts = {
        "none": NoContract(),
        "surprise": SurpriseContract(doc_freq, threshold),
        "oracle": OracleContract(valid_terms_by_step),
    }
    results = compare(
        steps_factory,
        contracts,
        is_goal_correct,
        is_step_correct=is_step_correct,
        trials=trials,
        keys=list(range(depth)),
        max_redo=max_redo,
    )
    return coverage, results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=400)
    parser.add_argument("--domains", type=int, default=6)
    parser.add_argument("--docs", type=int, default=120)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument("--p", type=float, default=0.08)
    parser.add_argument("--decoy-share", type=float, default=0.35)
    parser.add_argument("--threshold", type=int, default=1)
    parser.add_argument("--trials", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-redo", type=int, default=3)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    if not args.sweep:
        coverage, results = run_config(
            n_terms=args.terms,
            n_domains=args.domains,
            docs=args.docs,
            depth=args.depth,
            p=args.p,
            decoy_share=args.decoy_share,
            threshold=args.threshold,
            trials=args.trials,
            seed=args.seed,
            max_redo=args.max_redo,
        )
        print(
            f"statistical border | {args.domains} domains x {args.docs} docs "
            f"| coverage {coverage}/{args.terms} | depth={args.depth} "
            f"p={args.p} decoy-share={args.decoy_share}\n"
        )
        print(report(results))
        payload = {"coverage": coverage, "results": results}
    else:
        payload = {"sweep": {}}
        print("corpus-coverage sweep\n")
        for docs in (120, 40, 15, 6):
            coverage, results = run_config(
                n_terms=args.terms,
                n_domains=args.domains,
                docs=docs,
                depth=args.depth,
                p=args.p,
                decoy_share=args.decoy_share,
                threshold=args.threshold,
                trials=args.trials,
                seed=args.seed,
                max_redo=args.max_redo,
            )
            payload["sweep"][str(docs)] = {
                "coverage": coverage,
                "results": results,
            }
            print(f"docs/domain={docs} coverage={coverage}/{args.terms}")
            print(report(results))
            print()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
