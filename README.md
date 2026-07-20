# fedpath — federated path reasoning

**Borders stop errors from propagating along a reasoning path.**

A long reasoning path — a chain of thought, an agent's plan, a
multi-step derivation — usually runs *monolithically*: whatever one step
produces flows onward unchecked. That makes a single bad intermediate
result catastrophic, because everything downstream inherits it.
Correctness decays roughly as `(1 - p)^depth` in the per-step error rate
`p`: the deeper you reason, the more certainly something goes wrong, and
the more thoroughly one early mistake contaminates the conclusion.

A **federated path** treats each step as an isolated domain. A step
reasons privately; its output may cross to the next step only if it
passes a **border contract** — a cheap check, independent of the step's
internal work, that the value has to satisfy. Values failing the
contract are rejected at the border and the step is re-derived *from its
original input*, within a bounded budget. Errors are contained where
they arise rather than propagating.

This repository is a small, dependency-free library and two measured
experiments testing that claim honestly.

## Result

Both experiments compare border policies over identical fault streams
and score everything against independent ground truth.

**Exact algebraic border** (`experiments/exact_border.py`) — a 12-step
arithmetic path, 6% per-step corruption. The contract is a residue
check: because residues are a homomorphism for `+`, `-`, `*`, the
correct residue at each step is derivable without redoing the step.

| border | goal correct | work | rejections | false rejections |
|---|---|---|---|---|
| none | 44.8% | 12.0 | – | – |
| **residue** | **100.0%** | 12.8 | 0.79 | 0.01 |

**+55 points for +7% work.** (Unchecked theory predicts
`(1-0.06)^12 = 47.6%`; measured 44.8%.)

**Statistical border** (`experiments/statistical_border.py`) — a 10-step
path over a technical domain where each step emits a claim (a set of
terms) and, with probability 0.08, *fabricates* a plausible term that
does not exist. Fabrications propagate. Six domains each hold a private
corpus and publish **only document-frequency counts**; the federation
aggregates them. The border rejects claims containing terms that are
anomalously rare relative to the ensemble — high inverse document
frequency, i.e. surprising given what the federation collectively knows.

| border | goal clean | work | rejections | false rejections |
|---|---|---|---|---|
| none | 74.5% | 10.0 | – | – |
| **surprise (IDF)** | **100.0%** | 11.2 | 1.15 | 0.26 |
| oracle (upper bound) | 100.0% | 10.9 | 0.87 | 0.00 |

**+25.5 points, closing the entire gap to a perfect border**, for ~12%
extra work — using a statistic that crosses a federation boundary
without exposing any domain's data.

This matters because exact interface checks are rare in real reasoning.
A *statistical* contract is enough.

## The cost side (measured, not assumed)

A statistical contract is a **classifier**, so its false rejections must
be reported. They are driven by corpus coverage: rare-but-real terms the
federation has never seen look exactly like fabrications.

| docs/domain | coverage | goal clean | work | false rejections |
|---|---|---|---|---|
| 120 | 342/400 | 100.0% | 11.2 | 0.27 |
| 40 | 241/400 | 100.0% | 12.0 | 0.97 |
| 15 | 147/400 | 100.0% | 13.2 | 2.07 |
| 6 | 89/400 | 99.6% | 14.9 | 3.56 |

Containment holds as coverage thins; the price is paid in unnecessary
re-derivation, **not in wrong answers**. That is the correct direction
for a border to fail: conservative, never permissive.

## Install and run

No dependencies, Python 3.8+.

```bash
git clone https://github.com/<you>/fedpath
cd fedpath
python3 experiments/exact_border.py --depth 12 --p 0.06
python3 experiments/statistical_border.py
python3 experiments/statistical_border.py --sweep
```

## Using it

```python
from fedpath import SurpriseContract, run_path

# each domain keeps its corpus; only counts cross the border
df = SurpriseContract.federate([domain_a_docs, domain_b_docs])
border = SurpriseContract(df, threshold=1)

result = run_path(steps, border, is_correct=check, max_redo=3)
print(result.correct, result.work, result.false_rejections)
```

`Contract` is the extension point. A good border contract is:

- **cheap** relative to re-deriving the step,
- **independent** of the step's internal work (no circular re-checking),
- **partial** is fine — catching some errors beats catching none,
- **conservative** — better to re-derive an honest claim than to pass a
  fabricated one.

Practical candidates in real systems: type and unit/dimensional
constraints, algebraic or conservation invariants, cross-consistency
between redundantly derived values, retrieval or tool confirmation, and
surprise scores against a corpus the reasoner did not itself produce.

## Honest limits

1. **Fault model is random, not adversarial.** Systematic or
   adversarial fabrication designed to satisfy the contract defeats a
   surprise-based border by construction.
2. **At `threshold=1` the statistical check is close to "have I ever
   seen this?"**, which catches this fault model's fabrications almost
   by definition. Fabrications colliding with *common* real terms are
   not tested here and would erode the result toward the `none` row.
3. **These are computation and term-set paths, not natural language.**
   Mapping real reasoning steps onto checkable boundary values is
   unsolved and is where this idea will live or die.
4. **Bounded re-derivation assumes a step can succeed on retry.** A step
   that is deterministically wrong cannot be repaired by repetition;
   the border will correctly refuse and the path should fail loudly
   rather than pass a bad value.

## Why this framing

The principle is old and extremely robust — fault isolation through
verified interfaces is why bulkheads, sandboxes, checksums, type systems
and service boundaries work. It has simply not been applied
systematically to the *internal structure of machine reasoning*, where
the dominant architecture is still one long unchecked chain.

The federated framing adds one thing: **the border can be built from
information that crosses domains without the domains exposing
themselves.** Inverse document frequency is the canonical example — a
purely local statistic (term frequency) combined with a purely
collective one (document frequency), where only counts need to travel.
That makes verified borders feasible between parties that cannot or will
not share their data.

## License

MIT — see [LICENSE](LICENSE). Use it freely, including commercially.

## Acknowledgements

Developed by Brian Ramos, in collaboration with Claude (Anthropic),
which co-designed the experiments, wrote most of this code, and — for
the record — was wrong twice before this worked. Two earlier approaches
were tested and abandoned: one confirmed only a well-known property of
exact local search, and one produced a clean negative result. The
architecture here is the third idea, and the first that survived
measurement.

If you find a fault model where borders fail, please open an issue. A
negative result against this claim is as useful as the claim.
