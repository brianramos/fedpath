"""Immutable attempt-indexed plans for paired policy evaluation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

Token = TypeVar("Token")


@dataclass(frozen=True)
class AttemptPlan(Generic[Token]):
    """A token for every trial, step, and possible attempt."""

    trials: tuple[tuple[tuple[Token, ...], ...], ...]

    @classmethod
    def from_nested(
        cls, values: Iterable[Iterable[Iterable[Token]]]
    ) -> AttemptPlan[Token]:
        return cls(
            tuple(tuple(tuple(attempts) for attempts in trial) for trial in values)
        )

    def attempts(self, trial_index: int, step_index: int) -> tuple[Token, ...]:
        return self.trials[trial_index][step_index]


class PlannedStep(Generic[Token]):
    """A step that consumes a pre-generated token for each attempt."""

    def __init__(
        self,
        tokens: Sequence[Token],
        apply: Callable[[Any, Token], Any],
    ) -> None:
        if not tokens:
            raise ValueError("a planned step needs at least one attempt token")
        self._tokens = tuple(tokens)
        self._apply = apply
        self._attempt_index = 0

    def __call__(self, incoming: Any) -> Any:
        if self._attempt_index >= len(self._tokens):
            raise RuntimeError("attempt plan exhausted before the retry budget")
        token = self._tokens[self._attempt_index]
        self._attempt_index += 1
        return self._apply(incoming, token)
