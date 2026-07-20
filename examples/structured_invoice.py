"""Executable-assertion borders around a structured invoice workflow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fedpath import Contract, run_path


@dataclass(frozen=True)
class LineItem:
    sku: str
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class Invoice:
    lines: tuple[LineItem, ...]
    subtotal_cents: int | None = None
    tax_rate: Decimal = Decimal("0.0825")
    tax_cents: int | None = None
    total_cents: int | None = None


class InvoiceContract(Contract):
    """Independent schema, unit, and arithmetic checks at every boundary."""

    def check(self, key: str, value: Any) -> bool:
        if not isinstance(value, Invoice):
            return False
        if any(line.quantity <= 0 or line.unit_price_cents < 0 for line in value.lines):
            return False

        expected_subtotal = sum(
            line.quantity * line.unit_price_cents for line in value.lines
        )
        if key in {"subtotal", "tax", "total"}:
            if value.subtotal_cents != expected_subtotal:
                return False

        if key in {"tax", "total"}:
            expected_tax = int(
                (Decimal(expected_subtotal) * value.tax_rate).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            if value.tax_cents != expected_tax:
                return False

        if key == "total":
            if value.total_cents != value.subtotal_cents + value.tax_cents:
                return False
        return True


def main() -> None:
    source = Invoice(
        lines=(
            LineItem("A-17", 2, 1299),
            LineItem("B-04", 1, 750),
        )
    )
    tax_attempts = iter([999, 276])  # first result is intentionally wrong

    def load(_: Any) -> Invoice:
        return source

    def subtotal(invoice: Invoice) -> Invoice:
        amount = sum(line.quantity * line.unit_price_cents for line in invoice.lines)
        return replace(invoice, subtotal_cents=amount)

    def tax(invoice: Invoice) -> Invoice:
        return replace(invoice, tax_cents=next(tax_attempts))

    def total(invoice: Invoice) -> Invoice:
        return replace(
            invoice,
            total_cents=invoice.subtotal_cents + invoice.tax_cents,
        )

    result = run_path(
        [load, subtotal, tax, total],
        InvoiceContract(),
        lambda invoice: invoice.total_cents == 3624,
        is_step_correct=lambda index, incoming, candidate: InvoiceContract().check(
            ("load", "subtotal", "tax", "total")[index], candidate
        ),
        keys=("load", "subtotal", "tax", "total"),
        keep_trace=True,
    )
    print(result)


if __name__ == "__main__":
    main()
