"""
Experiment 1 - an exact algebraic border.

A chain of arithmetic steps stands in for a reasoning path: step i
transforms the running value with a known operation, and with
probability p its internal work is corrupted. The goal is the value at
the end of the chain.

Border contract: a residue check. Because residues are a homomorphism
for +, - and *, the correct residue at each step is derivable from the
step's definition, so a border can constrain a passed value without
redoing the step's work. The check is partial: corruptions that preserve
the residue cross undetected.

    python3 experiments/exact_border.py --depth 12 --p 0.06
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from fedpath import NoContract, ResidueContract, compare, report  # noqa

OPS = {
    'add': lambda v, k: v + k,
    'sub': lambda v, k: v - k,
    'mul': lambda v, k: v * k,
}


def build_chain(depth, seed):
    """A fixed, known sequence of operations: the 'program' of the path."""
    rng = random.Random(seed)
    return [(rng.choice(['add', 'sub', 'mul']), rng.randint(2, 9))
            for _ in range(depth)]


def truth_trace(chain, start=1):
    """Correct value after each step: ground truth for scoring, and the
    source of each border's expected residue."""
    vals, v = [], start
    for op, k in chain:
        v = OPS[op](v, k)
        vals.append(v)
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--depth', type=int, default=12)
    ap.add_argument('--p', type=float, default=0.06)
    ap.add_argument('--modulus', type=int, default=7)
    ap.add_argument('--trials', type=int, default=400)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()

    chain = build_chain(a.depth, a.seed)
    truth = truth_trace(chain)
    target = truth[-1]
    counter = {'t': 0}

    def factory():
        counter['t'] += 1
        rng = random.Random(a.seed * 100000 + counter['t'])

        def make(op, k):
            def step(prev):
                v = OPS[op](1 if prev is None else prev, k)
                if rng.random() < a.p:
                    v += rng.choice([-3, -2, -1, 1, 2, 3, 5])
                return v
            return step
        return [make(op, k) for op, k in chain]

    contracts = {
        'none': NoContract(),
        'residue': ResidueContract(a.modulus,
                                   lambda i: truth[i] % a.modulus),
    }
    res = compare(factory, contracts, lambda v: v == target,
                  trials=a.trials, keys=list(range(a.depth)))
    print(f'exact algebraic border | depth={a.depth} p={a.p} '
          f'mod={a.modulus} | {a.trials} trials\n')
    print(report(res))
    lift = res['residue']['correct_pct'] - res['none']['correct_pct']
    print(f'\nborder lift: {lift:+.1f} percentage points at '
          f'{res["residue"]["work"] - res["none"]["work"]:+.1f} work '
          f'per path')
    print(f'unchecked decay (1-p)^depth = '
          f'{100 * (1 - a.p) ** a.depth:.1f}% (theory) vs '
          f'{res["none"]["correct_pct"]:.1f}% (measured)')


if __name__ == '__main__':
    main()
