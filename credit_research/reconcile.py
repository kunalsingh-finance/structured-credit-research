"""Exact historical certificate arithmetic, without a contractual waterfall model.

Amounts are ordinary nonnegative decimal-dollar strings with at most two decimal
places. All calculations use integer cents. A missing operand causes SKIPPED;
absence never means zero. PASS means an individual reported-data identity agrees
exactly, not that a transaction's legal terms, economics, or forecasts are valid.

Certificate dates must describe a complete calendar collection month whose end
precedes the distribution date. Extra top-level metadata is preserved by callers;
this module neither changes source facts nor repairs source-label exceptions.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

AMOUNT_FIELDS = frozenset({
    "pool_begin", "principal_collected", "defaults", "repurchases", "pool_end",
    "interest_collected", "recoveries", "investment_income", "available_collections",
    "servicing_fee", "trustee_fee", "total_note_interest", "total_note_principal",
    "reserve_deposit", "residual_distribution", "reserve_draw", "total_distributions",
    "note_begin", "note_end", "reserve_begin", "reserve_interest", "reserve_release",
    "reserve_end", "gross_loss", "net_loss",
})
METADATA_FIELDS = (
    "deal_id", "collection_period_start", "collection_period_end",
    "distribution_date", "source_url", "extraction_method",
)
_MONEY = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?", flags=re.ASCII)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", flags=re.ASCII)
STATUSES = frozenset({"PASS", "FAIL", "SKIPPED"})


class CertificateError(ValueError):
    """The certificate schema, date convention, or supplied amount is invalid."""


def parse_amount(value: Any, field_name: str = "amount") -> int:
    """Parse USD into exact integer cents; never accept an inferred or rounded value.

    Only strings such as '0', '12.3', or '12.30' are accepted. Reject floats,
    integers, booleans, signs, whitespace, exponent notation, comma separators,
    currency symbols, nonfinite values, and fractions of a cent. All supported
    fields are nonnegative reported magnitudes; subtraction belongs to the rule.
    """
    if not isinstance(value, str) or _MONEY.fullmatch(value) is None:
        raise CertificateError(
            f"{field_name} must be a nonnegative ordinary decimal-dollar string "
            "with at most two fractional digits"
        )
    whole, separator, fractional = value.partition(".")
    try:
        cents = int(whole) * 100 + (int(fractional.ljust(2, "0")) if separator else 0)
    except ValueError as error:
        raise CertificateError(f"{field_name} exceeds the supported integer digit length") from error
    return cents


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise CertificateError(f"{field_name} must be a valid YYYY-MM-DD string")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CertificateError(f"{field_name} must be a valid YYYY-MM-DD date") from error


def _validate_metadata(certificate: Mapping[str, Any]) -> None:
    for field in METADATA_FIELDS:
        value = certificate.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CertificateError(f"{field} is required and must be a nonempty string")
    start = _parse_date(certificate["collection_period_start"], "collection_period_start")
    end = _parse_date(certificate["collection_period_end"], "collection_period_end")
    distribution = _parse_date(certificate["distribution_date"], "distribution_date")
    if not start <= end < distribution:
        raise CertificateError("Dates must satisfy collection start <= end < distribution date")
    last_day = calendar.monthrange(start.year, start.month)[1]
    if start.day != 1 or (end.year, end.month) != (start.year, start.month) or end.day != last_day:
        raise CertificateError("Collection period must be one complete calendar month")


@dataclass(frozen=True)
class _Rule:
    check_id: str
    name: str
    terms: tuple[tuple[str, int], ...]
    reported_field: str
    formula: str

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field for field, _ in self.terms) + (self.reported_field,)


RULES = (
    _Rule(
        "pool_rollforward", "Pool principal roll-forward",
        (("pool_begin", 1), ("principal_collected", -1), ("defaults", -1), ("repurchases", -1)),
        "pool_end", "pool_begin - principal_collected - defaults - repurchases = pool_end",
    ),
    _Rule(
        "collections_total", "Reported collection components",
        (("interest_collected", 1), ("principal_collected", 1), ("recoveries", 1),
         ("investment_income", 1), ("repurchases", 1)),
        "available_collections",
        "interest_collected + principal_collected + recoveries + investment_income + repurchases = available_collections",
    ),
    _Rule(
        "collections_to_distributions", "Collections and reserve draws to distributions",
        (("available_collections", 1), ("reserve_draw", 1)), "total_distributions",
        "available_collections + reserve_draw = total_distributions",
    ),
    _Rule(
        "distribution_components", "Reported distribution components",
        (("servicing_fee", 1), ("trustee_fee", 1), ("total_note_interest", 1),
         ("total_note_principal", 1), ("reserve_deposit", 1), ("residual_distribution", 1)),
        "total_distributions",
        "servicing_fee + trustee_fee + total_note_interest + total_note_principal + reserve_deposit + residual_distribution = total_distributions",
    ),
    _Rule(
        "note_rollforward", "Note principal roll-forward",
        (("note_begin", 1), ("total_note_principal", -1)), "note_end",
        "note_begin - total_note_principal = note_end",
    ),
    _Rule(
        "reserve_rollforward", "Reserve balance roll-forward",
        (("reserve_begin", 1), ("reserve_interest", 1), ("reserve_deposit", 1),
         ("reserve_draw", -1), ("reserve_release", -1)), "reserve_end",
        "reserve_begin + reserve_interest + reserve_deposit - reserve_draw - reserve_release = reserve_end",
    ),
    _Rule(
        "net_loss", "Gross losses less recoveries",
        (("gross_loss", 1), ("recoveries", -1)), "net_loss",
        "gross_loss - recoveries = net_loss",
    ),
)


def reconcile(certificate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return seven exact-cent arithmetic check rows for one historical certificate.

    Required metadata: deal_id, collection_period_start/end, distribution_date,
    source_url, extraction_method. Optional reported fields live in an amounts
    mapping. Every supplied amount must be a valid known-field decimal string;
    a supplied null/float is invalid, while an absent field makes affected checks
    SKIPPED. Unknown amount keys fail to expose extraction or spelling errors.

    Each result includes check_id, name, status, formula, required_fields,
    missing_fields, computed_cents, reported_cents, residual_cents, and reason.
    residual_cents = computed minus reported, with exactly zero required for PASS.
    SKIPPED amounts/residuals are None. No tolerance, implicit zero, adjustments,
    contractual waterfall reconstruction, or forecast is applied.
    """
    if not isinstance(certificate, Mapping):
        raise CertificateError("Certificate must be an object")
    _validate_metadata(certificate)
    supplied = certificate.get("amounts")
    if not isinstance(supplied, Mapping):
        raise CertificateError("Certificate amounts must be an object")
    unknown = set(supplied) - AMOUNT_FIELDS
    if unknown:
        raise CertificateError(f"Unknown amount fields: {', '.join(sorted(map(str, unknown)))}")
    amounts = {field: parse_amount(value, f"amounts.{field}") for field, value in supplied.items()}
    rows = []
    for rule in RULES:
        missing = [field for field in rule.required_fields if field not in amounts]
        row: dict[str, Any] = {
            "check_id": rule.check_id, "name": rule.name, "formula": rule.formula,
            "required_fields": list(rule.required_fields), "missing_fields": missing,
            "computed_cents": None, "reported_cents": None, "residual_cents": None,
        }
        if missing:
            row.update(status="SKIPPED", reason=f"Missing operands: {', '.join(missing)}. No result inferred.")
        else:
            computed = sum(amounts[field] * sign for field, sign in rule.terms)
            reported = amounts[rule.reported_field]
            residual = computed - reported
            row.update(
                status="PASS" if residual == 0 else "FAIL", computed_cents=computed,
                reported_cents=reported, residual_cents=residual,
                reason="Exact reported-data identity; residual 0 cents." if residual == 0
                else f"Reported-data identity differs by {residual:+d} cents (computed minus reported).",
            )
        rows.append(row)
    return rows


def summarize(checks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Count PASS/FAIL/SKIPPED rows; missing coverage can never mean overall PASS.

    Overall status is FAIL if any row fails, PASS only for a nonempty collection
    of exclusively passing checks, otherwise INCOMPLETE (including no checks).
    Combine multiple certificates by flattening their check rows before calling.
    Invalid/missing check statuses raise CertificateError rather than disappear.
    """
    if not isinstance(checks, Iterable):
        raise CertificateError("Summary checks must be an iterable of check rows")
    counts = {"PASS": 0, "FAIL": 0, "SKIPPED": 0}
    for check in checks:
        status = check.get("status") if isinstance(check, Mapping) else None
        if not isinstance(status, str) or status not in STATUSES:
            raise CertificateError("Every summary row must have PASS, FAIL, or SKIPPED status")
        counts[status] += 1
    total = sum(counts.values())
    status = "FAIL" if counts["FAIL"] else ("PASS" if total and not counts["SKIPPED"] else "INCOMPLETE")
    return {**counts, "total": total, "status": status}
