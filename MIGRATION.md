# Migrating from 0.1 to 0.2

## `run_path`

`run_path` now fails closed. Exhausting retries raises `BorderExhausted` by
default; `on_exhausted="return"` returns `PathResult(accepted=False)` without
calling later steps.

The final scoring callback is now named `is_goal_correct`. To measure false
rejections, pass a separate step oracle:

```python
result = run_path(
    steps,
    contract,
    is_goal_correct=goal_oracle,
    is_step_correct=step_oracle,
)
```

`PathResult.step_evaluations` replaces the ambiguous `work` metric. `work`
remains a read-only alias.

## `compare`

The factory now receives `trial_index`. It is called for every policy with the
same index:

```python
def steps_factory(trial_index):
    return build_steps_from_immutable_plan(plans[trial_index])
```

Do not use hidden mutable counters or one shared RNG across path steps.
Attempt-indexed plans are available through `AttemptPlan` and `PlannedStep`.

## Federated counts

Prefer the explicit two-stage API:

```python
released = local_document_frequency(private_documents)
aggregate = aggregate_document_frequencies(released_maps)
```

`SurpriseContract.federate` remains as an in-process compatibility helper, but
it should not be interpreted as a privacy mechanism.
