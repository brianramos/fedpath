# Changelog

## 0.2.0

- Fail closed on border exhaustion; rejected values never reach downstream steps.
- Separate goal correctness from per-step correctness for valid false-rejection metrics.
- Compare policies using shared trial indices and immutable attempt-indexed fault plans.
- Rename `work` to `step_evaluations` and measure contract evaluations separately.
- Add Wilson confidence intervals and exhaustion rates to experiment reports.
- Add residue-preserving and context-validating adversarial fault modes.
- Split local document-frequency computation from aggregation and document the threat model.
- Add package metadata, tests, CI, migration guidance, generated results, and a structured example.
