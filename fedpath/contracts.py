"""Built-in border contracts and explicit count-release helpers."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping
from typing import Any, Callable

from .core import Contract


class ResidueContract(Contract):
    """A partial algebraic contract based on a modular invariant."""

    def __init__(self, modulus: int, expected_residue: Callable[[Any], int]):
        if modulus <= 1:
            raise ValueError("modulus must be greater than 1")
        self.modulus = modulus
        self.expected_residue = expected_residue

    def check(self, key: Any, value: Any) -> bool:
        try:
            return value % self.modulus == self.expected_residue(key) % self.modulus
        except (TypeError, ValueError):
            return False


def local_document_frequency(
    documents: Iterable[Iterable[Hashable]],
) -> dict[Hashable, int]:
    """Compute document-frequency counts inside one data-holding domain."""

    counts: dict[Hashable, int] = {}
    for document in documents:
        for term in set(document):
            counts[term] = counts.get(term, 0) + 1
    return counts


def aggregate_document_frequencies(
    local_count_maps: Iterable[Mapping[Hashable, int]],
) -> dict[Hashable, int]:
    """Aggregate already-released local count maps.

    This function provides no secure aggregation or differential privacy. The
    caller is responsible for the transport and disclosure model.
    """

    aggregate: dict[Hashable, int] = {}
    for local_counts in local_count_maps:
        for term, count in local_counts.items():
            if not isinstance(count, int) or count < 0:
                raise ValueError(
                    "document-frequency counts must be non-negative integers"
                )
            aggregate[term] = aggregate.get(term, 0) + count
    return aggregate


class SurpriseContract(Contract):
    """Reject values containing terms below a document-frequency threshold."""

    def __init__(self, doc_freq: Mapping[Hashable, int], threshold: int = 1):
        if threshold < 0:
            raise ValueError("threshold must be non-negative")
        self.doc_freq = dict(doc_freq)
        self.threshold = threshold

    def check(self, key: Any, value: Iterable[Hashable]) -> bool:
        try:
            return all(self.doc_freq.get(term, 0) >= self.threshold for term in value)
        except TypeError:
            return False

    @staticmethod
    def federate(
        corpora: Iterable[Iterable[Iterable[Hashable]]],
    ) -> dict[Hashable, int]:
        """Compatibility helper for in-process demos.

        Production federation should call ``local_document_frequency`` in each
        domain and release only the resulting maps to
        ``aggregate_document_frequencies``.
        """

        return aggregate_document_frequencies(
            local_document_frequency(documents) for documents in corpora
        )
