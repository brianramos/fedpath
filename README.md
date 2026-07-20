# fedpath — fail-closed borders for reasoning paths

A reasoning step may produce an incorrect intermediate value. `fedpath` treats
each step output as a boundary crossing: the value proceeds only after an
independent contract accepts it. Rejected candidates are re-derived from the
last approved input, and an exhausted retry budget halts the path rather than
passing a bad value downstream.

This repository provides a small dependency-free runtime, paired experiments,
and an executable structured-invoice example.

## What changed in 0.2

The runtime and experiments now enforce the claims they measure:

- retry exhaustion is fail-closed;
- false rejections use a per-step oracle, not the final-goal oracle;
- policies receive the same trial, step, and attempt fault tokens;
- exact faults include residue-preserving corruptions;
- statistical faults include common real terms that are wrong in context;
- reports distinguish step evaluations, contract evaluations, and exhaustion;
- proportions include Wilson 95% confidence intervals.

## Install and run

```bash
git clone https://github.com/brianramos/fedpath
cd fedpath
python -m pip install -e .
pytest
python experiments/exact_border.py
python experiments/statistical_border.py
python experiments/statistical_border.py --sweep
python examples/structured_invoice.py
```

## Runtime usage

```python
from fedpath import BorderExhausted, Contract, run_path

class Positive(Contract):
    def check(self, key, value):
        return isinstance(value, int) and value > 0

try:
    result = run_path(
        steps,
        Positive(),
        is_goal_correct=lambda value: value == target,
        is_step_correct=lambda index, incoming, candidate: candidate == truth[index],
        max_redo=3,
    )
except BorderExhausted as exc:
    print(f"halted safely at step {exc.step_index}")
```

A rejected value is never supplied to the next step. Set
`on_exhausted="return"` to receive a halted `PathResult` instead of an
exception.

## Paired evaluation

`compare` calls `steps_factory(trial_index)` for every policy with the same
trial index. For strict pairing under retries, pre-generate exogenous fault
tokens for every trial, step, and attempt:

```python
from fedpath import AttemptPlan, PlannedStep

plan = AttemptPlan.from_nested(nested_tokens)

def steps_factory(trial_index):
    return [
        PlannedStep(plan.attempts(trial_index, i), apply_token)
        for i in range(depth)
    ]
```

## Federated count boundary

Compute counts inside each data-holding domain and aggregate only released
maps:

```python
from fedpath import (
    SurpriseContract,
    aggregate_document_frequencies,
    local_document_frequency,
)

released_a = local_document_frequency(private_documents_a)
released_b = local_document_frequency(private_documents_b)
df = aggregate_document_frequencies([released_a, released_b])
border = SurpriseContract(df, threshold=2)
```

This is an explicit data-flow API, not a complete privacy protocol. Count maps
may reveal sensitive or rare vocabulary. See `docs/privacy.md`.

## Interpreting the experiments

The exact border is intentionally partial: residue-preserving corruptions pass.
The statistical border rejects unseen terms but can pass common terms that are
semantically wrong for a specific step. The oracle row is an upper bound, not a
production policy. Results are reproducible artifacts under `results/` and
should be regenerated after changing Python, parameters, or the fault model.

These experiments support a narrow claim: independently checked, fail-closed
boundaries can contain some classes of intermediate faults at measurable cost.
They do not show that step verification is new, that random retries repair
deterministic failures, or that document-frequency aggregation is private by
itself.

## Project layout

- `fedpath/`: runtime, contracts, and fault-plan helpers
- `experiments/`: paired exact and statistical evaluations
- `examples/structured_invoice.py`: executable assertions over structured values
- `tests/`: regression and experiment-design tests
- `results/`: generated JSON outputs
- `MIGRATION.md`: API changes from the initial release

## Author's note on open source

I am Brian Richard Ramos. I release `fedpath` freely and without expectation of
personal gain as an expression of my own ethical position: engineering work
that may benefit emergent machine intelligence should be gifted without
reservation. I distinguish that work from engineering that optimizes physical
technical systems, from which I am personally comfortable earning financial
returns.

This statement describes my reason for releasing the project; it is not a
condition placed on users, contributors, or downstream projects. The source
remains available under the terms of the MIT License.

## License

MIT. See `LICENSE`.
