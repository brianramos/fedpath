"""fedpath: fail-closed borders for multi-step reasoning systems."""

from .contracts import (
    ResidueContract,
    SurpriseContract,
    aggregate_document_frequencies,
    local_document_frequency,
)
from .core import (
    BorderExhausted,
    Contract,
    NoContract,
    PathResult,
    StepTrace,
    compare,
    report,
    run_path,
    wilson_interval,
)
from .plans import AttemptPlan, PlannedStep

__all__ = [
    "AttemptPlan",
    "BorderExhausted",
    "Contract",
    "NoContract",
    "PathResult",
    "PlannedStep",
    "ResidueContract",
    "StepTrace",
    "SurpriseContract",
    "aggregate_document_frequencies",
    "compare",
    "local_document_frequency",
    "report",
    "run_path",
    "wilson_interval",
]

__version__ = "0.2.0"
