"""
Experiment 2 — a statistical border from federated corpus counts.

Exact interface checks are rare in real reasoning, so this asks the
harder question: does a *statistical* border still contain error?

Each step of the path emits a claim (a set of terms). With probability p
a step fabricates: it emits a plausible-looking term that does not
exist, and fabrications propagate downstream. Several domains each hold
a private corpus and publish only document-frequency counts; the
federation aggregates them. A claim is rejected at a border when a term
is anomalously rare relative to the ensemble - high inverse document
frequency, i.e. surprising given what the federation collectively knows.

Because the contract is a classifier, its false rejections are measured
explicitly, and the corpus-coverage sweep shows where its cost lands:
rare-but-real terms look exactly like fabrications when coverage is thin.

    python3 experiments/statistical_border.py --sweep
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from fedpath import (NoContract, SurpriseContract, compare,  # noqa
                     report)


def build_domain(n_terms, n_domains, docs_per_domain, seed):
    rng = random.Random(seed)
    terms = [f't{i}' for i in range(n_terms)]
    weights = [1.0 / (i + 1) ** 1.1 for i in range(n_terms)]
    corpora = []
    for _ in range(n_domains):
        docs = []
        for _ in range(docs_per_domain):
            docs.append(set(rng.choices(terms, weights=weights,
                                        k=rng.randint(3, 8))))
        corpora.append(docs)
    return terms, weights, corpora


class OracleContract:
    """Upper bound only: a perfect membership check, for reference."""

    def __init__(self, real):
        self.real = real

    def check(self, key, value):
        return all(t in self.real for t in value)


def run_config(n_terms, n_domains, docs, depth, p, threshold, trials,
               seed, quiet=False):
    terms, weights, corpora = build_domain(n_terms, n_domains, docs, seed)
    df = SurpriseContract.federate(corpora)
    real = set(terms)
    covered = sum(1 for t in terms if df.get(t, 0) > 0)

    counter = {'t': 0}

    def factory():
        counter['t'] += 1
        rng = random.Random(seed * 100000 + counter['t'])

        def step(prev):
            out = set(rng.sample(sorted(prev), min(2, len(prev)))) \
                if prev else set()
            if rng.random() < p:
                out.add(f'x{rng.randrange(100000)}')      # fabrication
            else:
                out.add(rng.choices(terms, weights=weights, k=1)[0])
            return out
        return [step] * depth

    contracts = {
        'none': NoContract(),
        'surprise': SurpriseContract(df, threshold),
        'oracle': OracleContract(real),
    }
    res = compare(factory, contracts,
                  lambda v: all(t in real for t in v), trials=trials)
    if not quiet:
        print(f'statistical border | {n_domains} domains x {docs} docs '
              f'| coverage {covered}/{n_terms} | depth={depth} p={p}\n')
        print(report(res))
        print(f'\nlift over no border: '
              f'{res["surprise"]["correct_pct"] - res["none"]["correct_pct"]:+.1f}'
              f' points | gap to oracle: '
              f'{res["oracle"]["correct_pct"] - res["surprise"]["correct_pct"]:+.1f}'
              f' points')
    return covered, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--terms', type=int, default=400)
    ap.add_argument('--domains', type=int, default=6)
    ap.add_argument('--docs', type=int, default=120)
    ap.add_argument('--depth', type=int, default=10)
    ap.add_argument('--p', type=float, default=0.08)
    ap.add_argument('--threshold', type=int, default=1)
    ap.add_argument('--trials', type=int, default=400)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--sweep', action='store_true',
                    help='corpus-coverage sweep: where the false '
                         'rejections come from')
    a = ap.parse_args()
    if not a.sweep:
        run_config(a.terms, a.domains, a.docs, a.depth, a.p,
                   a.threshold, a.trials, a.seed)
        return
    print('corpus-coverage sweep (the cost side of a statistical '
          'border)\n')
    print(f'{"docs/domain":>12} {"coverage":>10} {"correct":>9} '
          f'{"work":>7} {"false rej":>10}')
    for docs in (120, 40, 15, 6):
        cov, res = run_config(a.terms, a.domains, docs, a.depth, a.p,
                              a.threshold, a.trials, a.seed, quiet=True)
        r = res['surprise']
        print(f'{docs:>12} {cov:>6}/{a.terms} {r["correct_pct"]:>8.1f}% '
              f'{r["work"]:>7.1f} {r["false_rejections"]:>10.2f}')
    print('\nContainment holds as coverage thins; the price is paid in '
          'unnecessary\nre-derivation, not in wrong answers - the '
          'correct direction for a border to fail.')


if __name__ == '__main__':
    main()
