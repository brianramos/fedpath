"""
fedpath — federated path reasoning.

A reasoning path is a sequence (or DAG) of steps. In a monolithic path,
whatever one step emits flows onward unchecked, so a single bad
intermediate result contaminates everything downstream: correctness
decays roughly like (1 - p)^depth in the per-step error rate p.

A *federated* path treats each step as an isolated domain that reasons
privately and may only pass values across a **border** that verifies
them against a cheap contract. A value failing its contract is rejected
at the border and the step is re-derived locally, within a bounded
budget. Errors are then contained where they arise instead of
propagating along the path.

This module provides the minimal pieces:

    Contract      - a border check: cheap, independent of the producing
                    step's internal work, and allowed to be partial.
    ResidueContract   - exact algebraic contract (homomorphic invariant).
    SurpriseContract  - statistical contract from federated corpus
                        counts: reject values that are anomalously
                        surprising relative to the ensemble.
    run_path      - execute a path under a border policy and report
                    correctness, work, rejections and false rejections.

Nothing here assumes a particular reasoning engine: a "step" is any
callable that may be wrong with some probability.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


# --------------------------------------------------------------------------
# Contracts
# --------------------------------------------------------------------------
class Contract:
    """A border check.

    A contract must be (a) cheap relative to re-deriving the step and
    (b) computable *without* trusting the producing step's internal
    work. It is explicitly allowed to be partial: a border that catches
    some errors is worth far more than no border at all.
    """

    def check(self, key: Any, value: Any) -> bool:
        raise NotImplementedError


class NoContract(Contract):
    """Monolithic baseline: everything crosses."""

    def check(self, key, value):
        return True


class ResidueContract(Contract):
    """Exact algebraic border.

    Where step outputs are numbers combined by operations that commute
    with a modular reduction (+, -, *), the residue of a correct result
    is derivable from the residues of its inputs. A border can therefore
    constrain a passed value without recomputing the step. Corruptions
    that preserve the residue are not caught - the contract is partial by
    construction, as real interface checks are.
    """

    def __init__(self, modulus: int,
                 expected_residue: Callable[[Any], int]):
        self.m = modulus
        self.expected = expected_residue

    def check(self, key, value):
        return (value % self.m) == self.expected(key)


class SurpriseContract(Contract):
    """Statistical border built from federated corpus counts.

    Each participating domain holds a private corpus and publishes only
    document-frequency counts of the terms it has seen. The federation
    aggregates the counts; no document content crosses a border. A value
    (a set of terms) is rejected when any of its terms is anomalously
    rare relative to the ensemble - high inverse document frequency,
    i.e. surprising given what the federation collectively knows.

    This is a classifier, not an oracle. Rare-but-real terms will be
    rejected (false rejections); fabrications that collide with common
    terms will pass. Both must be measured, never assumed away.
    """

    def __init__(self, doc_freq: Dict[Any, int], threshold: int = 1):
        self.df = doc_freq
        self.threshold = threshold

    @staticmethod
    def federate(corpora: Iterable[Iterable[set]]) -> Dict[Any, int]:
        """Aggregate document-frequency counts across private corpora.

        Only counts cross the border; documents never leave their domain.
        """
        df: Dict[Any, int] = {}
        for docs in corpora:
            local: Dict[Any, int] = {}
            for doc in docs:
                for t in doc:
                    local[t] = local.get(t, 0) + 1
            for t, c in local.items():
                df[t] = df.get(t, 0) + c
        return df

    def check(self, key, value):
        return all(self.df.get(t, 0) >= self.threshold for t in value)


# --------------------------------------------------------------------------
# Path execution
# --------------------------------------------------------------------------
@dataclass
class PathResult:
    value: Any
    correct: bool
    work: int = 0
    rejections: int = 0
    false_rejections: int = 0
    trace: List[Any] = field(default_factory=list)


def run_path(steps: Sequence[Callable[[Any], Any]],
             contract: Contract,
             is_correct: Callable[[Any], bool],
             keys: Optional[Sequence[Any]] = None,
             max_redo: int = 3,
             keep_trace: bool = False) -> PathResult:
    """Execute a reasoning path under a border policy.

    steps       : callables; step(previous_value) -> value. A step may be
                  wrong with some probability - that is the point.
    contract    : border check applied to every value before it crosses.
    is_correct  : ground truth, used ONLY for scoring (never by the
                  border), so that false rejections can be measured.
    keys        : optional per-step keys handed to the contract.
    max_redo    : bounded local re-derivation budget per step.
    """
    value = None
    work = rejections = false_rejections = 0
    trace: List[Any] = []
    for i, step in enumerate(steps):
        key = keys[i] if keys is not None else i
        incoming = value          # the border-approved input to this step
        value = step(incoming)
        work += 1
        redos = 0
        while redos < max_redo and not contract.check(key, value):
            rejections += 1
            if is_correct(value):
                false_rejections += 1      # the border was wrong here
            # re-derive IN ISOLATION from the approved input; never feed
            # a rejected value back into the step
            value = step(incoming)
            work += 1
            redos += 1
        if keep_trace:
            trace.append(value)
    return PathResult(value=value, correct=is_correct(value), work=work,
                      rejections=rejections,
                      false_rejections=false_rejections, trace=trace)


def compare(steps_factory: Callable[[], Sequence[Callable]],
            contracts: Dict[str, Contract],
            is_correct: Callable[[Any], bool],
            trials: int = 200,
            keys: Optional[Sequence[Any]] = None,
            max_redo: int = 3) -> Dict[str, Dict[str, float]]:
    """Run every border policy over identical fault streams.

    steps_factory() must return a fresh, deterministically seeded step
    sequence, so that all policies face the same errors.
    """
    out: Dict[str, Dict[str, float]] = {}
    for name, contract in contracts.items():
        ok = work = rej = frej = 0
        for _ in range(trials):
            res = run_path(steps_factory(), contract, is_correct,
                           keys=keys, max_redo=max_redo)
            ok += res.correct
            work += res.work
            rej += res.rejections
            frej += res.false_rejections
        out[name] = {
            'correct_pct': 100.0 * ok / trials,
            'work': work / trials,
            'rejections': rej / trials,
            'false_rejections': frej / trials,
        }
    return out


def report(results: Dict[str, Dict[str, float]]) -> str:
    lines = [f'{"border":>14} {"goal correct":>13} {"work":>8} '
             f'{"rejects":>9} {"false rej":>10}']
    for name, r in results.items():
        lines.append(f'{name:>14} {r["correct_pct"]:>12.1f}% '
                     f'{r["work"]:>8.1f} {r["rejections"]:>9.2f} '
                     f'{r["false_rejections"]:>10.2f}')
    return '\n'.join(lines)
