"""Transparent collateral runoff assumptions feeding the contractual waterfall.

Amounts remain integer cents. Default/prepayment hazards act as competing events;
scheduled principal and prepayments cannot spend the same principal twice.
Recovery queues contain period flows, never repeated cumulative recoveries.
"""
from __future__ import annotations

import calendar
import math
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache


def cents(x: float | Decimal) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def add_months(day: date, months: int, target_day: int | None = None) -> date:
    m = day.year * 12 + day.month - 1 + months
    year, month = divmod(m, 12)
    month += 1
    return date(year, month, min(target_day or day.day, calendar.monthrange(year, month)[1]))


@lru_cache(maxsize=512)
def distribution_date(previous: str, offset: int) -> str:
    # Calendar supplied by pandas covers US federal bank holidays. This is a
    # documented scenario convention, not an independently observed future date.
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    base = add_months(date.fromisoformat(previous), offset, 15)
    holidays = {v.date() for v in USFederalHolidayCalendar().holidays(base, base + timedelta(days=7))}
    while base.weekday() >= 5 or base in holidays:
        base += timedelta(days=1)
    return base.isoformat()


def competing_monthly(annual_default: float, annual_prepay: float) -> tuple[float, float]:
    for n, v in (("annual_default", annual_default), ("annual_prepay", annual_prepay)):
        if not math.isfinite(v) or not 0 <= v < 1:
            raise ValueError(f"{n} must be a finite probability in [0,1)")
    d, p = -math.log1p(-annual_default) / 12, -math.log1p(-annual_prepay) / 12
    total = d + p
    if total == 0:
        return 0, 0
    event = -math.expm1(-total)
    return event * d / total, event * p / total


def make_cohorts(active, pool_cents: int) -> tuple[list[dict], dict]:
    """Contractual term/APR buckets preserve the current fleet's runoff spread."""
    import numpy as np
    import pandas as pd
    if active.empty or pool_cents <= 0:
        raise ValueError("A positive disclosed collateral pool is required")
    f = active.copy()
    missing_term = f.remaining_months.isna()
    matured_term = f.remaining_months.notna() & (f.remaining_months <= 0)
    known = f.loc[~missing_term & ~matured_term, "remaining_months"]
    if known.empty:
        raise ValueError("No disclosed remaining terms for collateral projection")
    term_fallback = int(round(float(known.median())))
    apr_fallback = float(f.interest_rate_pct.dropna().median())
    if not math.isfinite(apr_fallback):
        raise ValueError("No disclosed APR for collateral projection")
    if (f.remaining_months.dropna() > 120).any():
        raise ValueError("Remaining term above120months requires a separate projection convention")
    f["term"] = f.remaining_months.where(~missing_term, term_fallback).round().clip(lower=1).astype(int)
    f["apr"] = f.interest_rate_pct.fillna(apr_fallback).round(1)
    groups = f.groupby(["term", "apr"], observed=True).end_balance_cents.sum()
    source_total = int(groups.sum())
    if source_total != pool_cents:
        raise ValueError(f"Tape ending principal {source_total} must equal supplied mapped collateral {pool_cents}")
    f["reinstated"] = f.get("previously_defaulted", pd.Series(False, index=f.index)).astype(bool)
    groups = f.groupby(["term", "apr", "reinstated"], observed=True).end_balance_cents.sum()
    cohorts = [{"balance_cents": int(balance), "remaining_months": int(term), "apr": float(apr) / 100,
                "default_hazard_multiplier": 2.0 if reinstated else 1.0}
               for (term, apr, reinstated), balance in groups.items()]
    return cohorts, {"cohorts": len(cohorts), "missing_term_loans": int(missing_term.sum()),
                     "matured_positive_balance_loans": int(matured_term.sum()),
                     "missing_apr_loans": int(f.interest_rate_pct.isna().sum()),
                     "term_fallback_months": term_fallback, "apr_fallback_pct": apr_fallback,
                     "method": "Disclosure APR and remaining-term buckets, proportional competing-event attrition, recast annuity schedules; known matured claims assume next-period balloon collection unless defaulted"}


def project_collateral(cohorts: list[dict], previous_distribution: str, *, annual_default_rate: float,
                       annual_prepayment_rate: float, recovery_rate: float, recovery_lag_months: int,
                       interest_collection_factor: float = 1.0, floating_note_rate: str = "0.05",
                       horizon_months: int = 180, require_closed: bool = True) -> tuple[list[dict], list[dict]]:
    if not 0 <= recovery_rate <= 1 or not math.isfinite(recovery_rate):
        raise ValueError("Recovery fraction must lie in [0,1]")
    if type(recovery_lag_months) is not int or recovery_lag_months < 1:
        raise ValueError("Recovery lag must be a positive whole month")
    if not 0 <= interest_collection_factor <= 1:
        raise ValueError("Collection factor must lie in [0,1]")
    if not cohorts or horizon_months < 1:
        raise ValueError("A nonempty cohort set and positive horizon are required")
    d, p = competing_monthly(annual_default_rate, annual_prepayment_rate)
    working = [dict(c) for c in cohorts]
    for c in working:
        if type(c["balance_cents"]) is not int or c["balance_cents"] < 0 or c["remaining_months"] < 1 or not 0 <= c["apr"] < 1:
            raise ValueError("Invalid disclosed cohort assumptions")
        c["default_monthly"], c["prepay_monthly"] = competing_monthly(
            1 - (1 - annual_default_rate) ** c.get("default_hazard_multiplier", 1.0), annual_prepayment_rate)
    recovery_queue: dict[int, int] = {}
    rows, periods = [], []
    for month in range(1, horizon_months + 1):
        beginning = sum(c["balance_cents"] for c in working)
        default = prepay = scheduled = interest = 0
        for c in working:
            bal = c["balance_cents"]
            if not bal:
                continue
            cd, cp = c["default_monthly"], c["prepay_monthly"]
            loss = min(bal, cents(bal * cd))
            paid = min(bal - loss, cents(bal * cp))
            performing = bal - loss - paid
            monthly_apr = c["apr"] / 12
            term = c["remaining_months"]
            if term <= 1:
                amort = performing
            elif monthly_apr:
                annuity = performing * monthly_apr / (1 - (1 + monthly_apr) ** -term)
                amort = min(performing, max(0, cents(annuity - performing * monthly_apr)))
            else:
                amort = min(performing, cents(performing / term))
            earned = cents((bal - (loss + paid) / 2) * monthly_apr * interest_collection_factor)
            c["balance_cents"] = performing - amort
            c["remaining_months"] = max(1, term - 1)
            default += loss
            prepay += paid
            scheduled += amort
            interest += earned
        end = sum(c["balance_cents"] for c in working)
        recovery_queue[month + recovery_lag_months] = cents(default * recovery_rate)
        recovery = recovery_queue.pop(month, 0)
        # Remove zero pending flows; horizon closure must track cash still due.
        recovery_queue = {k: v for k, v in recovery_queue.items() if v}
        principal = scheduled + prepay
        if beginning - principal - default != end:
            raise AssertionError("Collateral principal is not conserved")
        dist = distribution_date(previous_distribution, month)
        periods.append({"distribution_date": dist, "pool_end": end, "principal_collected": principal,
                        "interest_collected": interest, "recoveries": recovery, "defaults": default,
                        "prepayments": prepay, "floating_note_rate": floating_note_rate})
        rows.append({"month": month, "distribution_date": dist,
                     "pool_begin_cents": beginning, "pool_end_cents": end,
                     "scheduled_principal_cents": scheduled, "prepayment_cents": prepay,
                     "default_cents": default, "recovery_cents": recovery,
                     "interest_cents": interest, "available_cash_cents": principal + interest + recovery,
                     "net_loss_cents": default - recovery})
        if end == 0 and not recovery_queue:
            break
    if require_closed and (rows[-1]["pool_end_cents"] or recovery_queue):
        raise ValueError("Collateral horizon did not exhaust all principal and recovery flows")
    return periods, rows
