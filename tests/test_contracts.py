import pytest

from fedpath import (
    ResidueContract,
    SurpriseContract,
    aggregate_document_frequencies,
    local_document_frequency,
)


def test_local_document_frequency_counts_each_term_once_per_document():
    counts = local_document_frequency(
        [
            ["a", "a", "b"],
            ["a", "c"],
        ]
    )
    assert counts == {"a": 2, "b": 1, "c": 1}


def test_aggregate_document_frequencies_accepts_only_released_counts():
    assert aggregate_document_frequencies(
        [
            {"a": 2, "b": 1},
            {"a": 3, "c": 1},
        ]
    ) == {"a": 5, "b": 1, "c": 1}

    with pytest.raises(ValueError):
        aggregate_document_frequencies([{"a": -1}])


def test_surprise_contract_and_residue_contract():
    assert SurpriseContract({"known": 2}, threshold=1).check(0, {"known"})
    assert not SurpriseContract({"known": 2}, threshold=1).check(0, {"new"})
    assert ResidueContract(7, lambda key: 3).check(0, 10)
    assert not ResidueContract(7, lambda key: 3).check(0, 11)
