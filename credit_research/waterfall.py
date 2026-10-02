"""Bounded pre-acceleration replay for CarMax Auto Owner Trust 2025-2.

This module is not a complete deal model. It accepts observed collateral cash,
beginning note balances, and the certificate's floating note rate. It excludes
acceleration, arrears, reserve draws, cleanup calls, additional fees, final-date
payments, and the initial stub period. Cash insufficient to fund any supported
waterfall step raises UnsupportedReplay; no partial-success result is returned.

All output monetary amounts are integer USD cents. Reserve earnings and their
release remain separate from the collection-account residual distribution.
No reported payment or expected-output field is used by the calculation.
The supplied floating rate is observed in the certificate, not independently
rebuilt from SOFR. Ambiguous source year labels must remain visible in reports.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re
from typing import Any


NOTES = ("A1", "A2a", "A2b", "A3", "A4", "B", "C", "D")
INITIAL_POOL_CENTS = 141_057_942_174
RESERVE_MINIMUM_CENTS = 352_644_855
FIRST_DISTRIBUTION_DATE = date(2025, 5, 15)
EARLIEST_FINAL_DATE = date(2026, 5, 15)
SCOPE = "bounded_fully_funded_pre_acceleration_replay"

_FIXED_MONTHLY_RATES = {
    "A2a": Decimal("0.0459"),
    "A3": Decimal("0.0448"),
    "A4": Decimal("0.0465"),
    "B": Decimal("0.0496"),
    "C": Decimal("0.0516"),
    "D": Decimal("0.0574"),
}
_MONEY_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?\Z")
_RATE_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


class UnsupportedReplay(ValueError):
    """The input or cash state is outside this replay's explicit scope."""


def _decimal_string(value: object, label: str, pattern: re.Pattern[str]) -> Decimal:
    if not isinstance(value, str) or len(value) > 50 or not pattern.fullmatch(value):
        raise UnsupportedReplay(f"{label} must be a nonnegative decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise UnsupportedReplay(f"{label} must be a finite decimal string") from exc
    if not amount.is_finite():
        raise UnsupportedReplay(f"{label} must be finite")
    return amount


def _cents(value: object, label: str) -> int:
    amount = _decimal_string(value, label, _MONEY_PATTERN)
    with localcontext() as context:
        context.prec = 80
        return int(amount * 100)


def _round_cents(amount_in_cents: Decimal) -> int:
    return int(amount_in_cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _iso_date(value: object, label: str) -> date:
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise UnsupportedReplay(f"{label} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise UnsupportedReplay(f"{label} is not a valid date") from exc


def _reject_optional_conditions(inputs: Mapping[str, object]) -> None:
    for flag in ("accelerated", "cleanup_call", "shortfalls"):
        if flag in inputs:
            if not isinstance(inputs[flag], bool):
                raise UnsupportedReplay(f"{flag} must be a boolean when provided")
            if inputs[flag]:
                raise UnsupportedReplay(f"{flag} is outside the replay scope")
    for field in (
        "arrears",
        "interest_arrears",
        "repurchase_fees",
        "additional_fees",
        "unreimbursed_servicer_advances",
        "reserve_draw",
    ):
        if field in inputs and _cents(inputs[field], field) != 0:
            raise UnsupportedReplay(f"nonzero {field} is outside the replay scope")


def _allocate_principal(total: int, balances: Mapping[str, int]) -> dict[str, int]:
    allocations = dict.fromkeys(NOTES, 0)
    remaining = total
    for group in (("A1",), ("A2a", "A2b"), ("A3",), ("A4",), ("B",), ("C",), ("D",)):
        group_balance = sum(balances[note] for note in group)
        paid = min(remaining, group_balance)
        if len(group) == 1:
            allocations[group[0]] = paid
        elif group_balance:
            with localcontext() as context:
                context.prec = 80
                first = _round_cents(Decimal(paid) * balances["A2a"] / group_balance)
            allocations["A2a"] = first
            allocations["A2b"] = paid - first
        remaining -= paid
    if remaining:
        raise AssertionError("principal allocation exceeds beginning note balances")
    return allocations


def replay(replay_inputs: Mapping[str, object]) -> dict[str, Any]:
    """Return cent-valued contractual payments or reject the unsupported case.

    Required input keys are pool_begin, pool_end, available_collections,
    reserve_begin, reserve_interest, prior_distribution_date, distribution_date,
    floating_note_rate, and note_begin (a mapping with precisely the NOTES keys).
    Monetary inputs are nonnegative decimal USD strings with at most two places.
    floating_note_rate is a nonnegative decimal fraction string, not a percent.

    The caller must verify the omitted deal conditions against its sources.
    Optional explicit unsupported flags/amounts are rejected when nonzero.
    Unrelated fields, including expected certificate outputs, are not read.
    """
    if not isinstance(replay_inputs, Mapping):
        raise UnsupportedReplay("replay_inputs must be a mapping")
    required = {
        "pool_begin", "pool_end", "available_collections", "reserve_begin",
        "reserve_interest", "prior_distribution_date", "distribution_date",
        "floating_note_rate", "note_begin",
    }
    missing = required.difference(replay_inputs)
    if missing:
        raise UnsupportedReplay("missing required inputs: " + ", ".join(sorted(missing)))
    _reject_optional_conditions(replay_inputs)
    money = {
        key: _cents(replay_inputs[key], key)
        for key in ("pool_begin", "pool_end", "available_collections", "reserve_begin", "reserve_interest")
    }
    if money["pool_begin"] <= 0 or money["pool_end"] <= 0:
        raise UnsupportedReplay("beginning and ending pool balances must be positive")
    if money["pool_end"] > money["pool_begin"]:
        raise UnsupportedReplay("pool growth is outside this amortizing-pool replay")
    raw_notes = replay_inputs["note_begin"]
    if not isinstance(raw_notes, Mapping) or set(raw_notes) != set(NOTES):
        raise UnsupportedReplay("note_begin must contain exactly " + ", ".join(NOTES))
    notes = {note: _cents(raw_notes[note], f"note_begin.{note}") for note in NOTES}
    total_notes = sum(notes.values())
    if total_notes <= 0:
        raise UnsupportedReplay("at least one note must be outstanding")
    prior = _iso_date(replay_inputs["prior_distribution_date"], "prior_distribution_date")
    current = _iso_date(replay_inputs["distribution_date"], "distribution_date")
    if prior < FIRST_DISTRIBUTION_DATE:
        raise UnsupportedReplay("the initial stub period is outside the replay scope")
    if current <= prior or current >= EARLIEST_FINAL_DATE:
        raise UnsupportedReplay("dates must advance and remain before 2026-05-15")
    if current.year * 12 + current.month != prior.year * 12 + prior.month + 1:
        raise UnsupportedReplay("only consecutive monthly distribution periods are supported")
    days = (current - prior).days
    rate = _decimal_string(replay_inputs["floating_note_rate"], "floating_note_rate", _RATE_PATTERN)

    with localcontext() as context:
        context.prec = 80
        servicing = _round_cents(Decimal(money["pool_begin"]) / 1200)
        interest = {
            note: _round_cents(Decimal(notes[note]) * fixed_rate / 12)
            for note, fixed_rate in _FIXED_MONTHLY_RATES.items()
        }
        interest["A1"] = _round_cents(Decimal(notes["A1"]) * Decimal("0.04468") * days / 360)
        interest["A2b"] = _round_cents(Decimal(notes["A2b"]) * rate * days / 360)
        oc_target = _round_cents(Decimal(INITIAL_POOL_CENTS) * Decimal("0.0075"))
    interest = {note: interest[note] for note in NOTES}
    class_a = sum(notes[note] for note in ("A1", "A2a", "A2b", "A3", "A4"))
    priority = max(class_a - money["pool_end"], 0)
    secondary = max(class_a + notes["B"] - money["pool_end"] - priority, 0)
    tertiary = max(class_a + notes["B"] + notes["C"] - money["pool_end"] - priority - secondary, 0)
    quaternary = max(total_notes - money["pool_end"] - priority - secondary - tertiary, 0)
    tiers = priority + secondary + tertiary + quaternary
    regular = min(total_notes - tiers, max(total_notes + oc_target - money["pool_end"] - tiers, 0))
    reserve_before_deposit = money["reserve_begin"] + money["reserve_interest"]
    reserve_deposit = max(RESERVE_MINIMUM_CENTS - reserve_before_deposit, 0)
    cash = money["available_collections"]

    def pay(amount: int, label: str) -> None:
        nonlocal cash
        if cash < amount:
            raise UnsupportedReplay(
                f"insufficient collection cash at {label}: needs {amount} cents, has {cash}; "
                "reserve draws and payment shortfalls are outside the replay scope"
            )
        cash -= amount

    pay(servicing, "servicing fee")
    pay(sum(interest[note] for note in ("A1", "A2a", "A2b", "A3", "A4")), "Class A interest")
    pay(priority, "priority principal")
    pay(interest["B"], "Class B interest")
    pay(secondary, "secondary principal")
    pay(interest["C"], "Class C interest")
    pay(tertiary, "tertiary principal")
    pay(interest["D"], "Class D interest")
    pay(quaternary, "quaternary principal")
    pay(reserve_deposit, "reserve top-up")
    pay(regular, "regular principal")

    total_principal = tiers + regular
    principal = _allocate_principal(total_principal, notes)
    note_end = {note: notes[note] - principal[note] for note in NOTES}
    reserve_release = max(reserve_before_deposit + reserve_deposit - RESERVE_MINIMUM_CENTS, 0)
    reserve_end = reserve_before_deposit + reserve_deposit - reserve_release
    return {
        "scope": SCOPE,
        "act_360_days": days,
        "contractual_oc_target": oc_target,
        "servicing_fee": servicing,
        "interest": interest,
        "principal": principal,
        "priority": priority,
        "secondary": secondary,
        "tertiary": tertiary,
        "quaternary": quaternary,
        "regular": regular,
        "total_note_interest": sum(interest.values()),
        "total_note_principal": total_principal,
        "note_end": note_end,
        "residual_distribution": cash,
        "reserve_deposit": reserve_deposit,
        "reserve_release": reserve_release,
        "reserve_end": reserve_end,
    }
