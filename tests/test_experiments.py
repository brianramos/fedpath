from experiments.exact_border import run_experiment
from experiments.statistical_border import run_config


def test_exact_experiment_is_paired_and_partial():
    results = run_experiment(trials=300, seed=3, preserving_share=0.5)
    assert results["residue"]["correct_pct"] > results["none"]["correct_pct"]
    assert results["residue"]["correct_pct"] < 100.0


def test_statistical_experiment_has_a_gap_to_oracle_with_decoys():
    _, results = run_config(trials=300, seed=4, decoy_share=0.7)
    assert results["surprise"]["correct_pct"] > results["none"]["correct_pct"]
    assert results["surprise"]["correct_pct"] < results["oracle"]["correct_pct"]
