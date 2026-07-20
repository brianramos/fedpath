# Generated results

The JSON files in this directory are generated from the checked-in experiment
code. Regenerate them with:

```bash
python experiments/exact_border.py --json results/exact.json
python experiments/statistical_border.py --json results/statistical.json
python experiments/statistical_border.py --sweep --json results/statistical-sweep.json
```

The files record measured outcomes for a fixed Python implementation and fixed
seeds. They are not universal performance claims.
