"""Stateful, cent-exact CAOT 2025-2 research cash-flow scenarios.

The executed May 1, 2025 sale/servicing agreement (SSA) and indenture,
filed in accession 0001193125-25-111714, supply the encoded priorities.
The original bounded historical ``waterfall.replay`` API is unchanged.

Collateral projections, recovery completion, floating coupons, call election,
and acceleration election are explicit caller assumptions, not predictions
made here. An interest shortfall does not automatically elect acceleration.
The model does not infer legal notices, remedies, consents or liquidation.
Unpaid principal is an economic terminal loss only after the caller declares
that all collateral and recoveries have run off. It is never cash received.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .waterfall import NOTES, INITIAL_POOL_CENTS, RESERVE_MINIMUM_CENTS


CLASS_A = NOTES[:5]
GROUPS = (("A1",), ("A2a", "A2b"), ("A3",), ("A4",), ("B",), ("C",), ("D",))
FIXED_RATES = {"A1": "0.04468", "A2a": "0.0459", "A3": "0.0448",
               "A4": "0.0465", "B": "0.0496", "C": "0.0516", "D": "0.0574"}
MATURITIES = {"A1": "2026-05-15", "A2a": "2028-07-17", "A2b": "2028-07-17",
              "A3": "2030-03-15", "A4": "2030-11-15", "B": "2030-11-15",
              "C": "2031-01-15", "D": "2031-10-15"}
SSA_URL = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex991.htm"
INDENTURE_URL = "https://www.sec.gov/Archives/edgar/data/1259380/000119312525111714/d943115dex41.htm"


def _zero_notes() -> dict[str, int]:
    return dict.fromkeys(NOTES, 0)


def _money(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be nonnegative integer USD cents")
    return value


def _note_map(value: Mapping[str, int], name: str) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(NOTES):
        raise ValueError(f"{name} must contain exactly {', '.join(NOTES)}")
    return {n: _money(value[n], f"{name}.{n}") for n in NOTES}


def _rate(value: str, name: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a nonnegative decimal fraction string")
    try:
        result = Decimal(value)
    except Exception as exc:
        raise ValueError(f"invalid {name}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"invalid {name}")
    return result


def _round(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class DealTerms:
    initial_pool_balance: int = INITIAL_POOL_CENTS
    reserve_minimum: int = RESERVE_MINIMUM_CENTS
    oc_rate: str = "0.0075"
    servicing_rate: str = "0.01"
    fixed_rates: Mapping[str, str] = field(default_factory=lambda: dict(FIXED_RATES))
    final_dates: Mapping[str, str] = field(default_factory=lambda: dict(MATURITIES))
    affiliated_servicer: bool = True
    accrue_interest_on_arrears: bool = True
    cleanup_threshold: str = "0.10"
    first_distribution_date: str = "2025-05-15"

    def __post_init__(self) -> None:
        _money(self.initial_pool_balance, "initial_pool_balance")
        _money(self.reserve_minimum, "reserve_minimum")
        for n in ("oc_rate", "servicing_rate", "cleanup_threshold"):
            _rate(getattr(self, n), n)
        if set(self.fixed_rates) != set(NOTES) - {"A2b"}:
            raise ValueError("fixed_rates must specify every fixed coupon")
        for n, v in self.fixed_rates.items():
            _rate(v, n)
        if set(self.final_dates) != set(NOTES):
            raise ValueError("final_dates must specify every note")
        for v in self.final_dates.values():
            date.fromisoformat(v)
        date.fromisoformat(self.first_distribution_date)
        if type(self.affiliated_servicer) is not bool or type(self.accrue_interest_on_arrears) is not bool:
            raise ValueError("term flags must be bool")


@dataclass(frozen=True)
class ScenarioState:
    pool_balance: int
    note_balances: Mapping[str, int]
    reserve_balance: int
    prior_distribution_date: str
    interest_arrears: Mapping[str, int] = field(default_factory=_zero_notes)
    overdue_interest_arrears: Mapping[str, int] = field(default_factory=_zero_notes)
    servicing_arrears: int = 0
    trustee_arrears: int = 0
    senior_expense_arrears: int = 0
    accelerated: bool = False
    acceleration_reason: str = ""

    def __post_init__(self) -> None:
        for n in ("pool_balance", "reserve_balance", "servicing_arrears", "trustee_arrears", "senior_expense_arrears"):
            _money(getattr(self, n), n)
        for n in ("note_balances", "interest_arrears", "overdue_interest_arrears"):
            _note_map(getattr(self, n), n)
        date.fromisoformat(self.prior_distribution_date)
        if type(self.accelerated) is not bool:
            raise ValueError("accelerated must be bool")
        if self.accelerated and self.acceleration_reason not in ("payment_or_bankruptcy", "covenant_or_representation"):
            raise ValueError("accelerated state requires a documented acceleration_reason")


@dataclass(frozen=True)
class CollateralPeriod:
    distribution_date: str
    pool_end: int
    principal_collected: int
    interest_collected: int
    recoveries: int = 0
    defaults: int = 0
    prepayments: int = 0
    repurchases: int = 0
    investment_income: int = 0
    reserve_interest: int = 0
    floating_note_rate: str = "0.05"
    trustee_fee: int = 0
    senior_expenses: int = 0
    accelerated: bool = False
    acceleration_reason: str = ""
    cleanup_elected: bool = False
    cleanup_price: int = 0
    cleanup_accrued_receivable_interest: int = 0
    cleanup_other_property_value: int = 0
    cleanup_notice_days: int = 0
    trust_termination: bool = False

    def __post_init__(self) -> None:
        for n in ("pool_end", "principal_collected", "interest_collected", "recoveries", "defaults",
                  "prepayments", "repurchases", "investment_income", "reserve_interest", "trustee_fee",
                  "senior_expenses", "cleanup_price", "cleanup_accrued_receivable_interest",
                  "cleanup_other_property_value", "cleanup_notice_days"):
            _money(getattr(self, n), n)
        if self.prepayments > self.principal_collected:
            raise ValueError("prepayments are a component of principal_collected")
        _rate(self.floating_note_rate, "floating_note_rate")
        date.fromisoformat(self.distribution_date)
        if any(type(getattr(self, n)) is not bool for n in ("accelerated", "cleanup_elected", "trust_termination")):
            raise ValueError("election flags must be bool")
        if self.accelerated and self.acceleration_reason not in ("payment_or_bankruptcy", "covenant_or_representation"):
            raise ValueError("acceleration requires its contractual default category")
        if not self.cleanup_elected and self.cleanup_price:
            raise ValueError("cleanup_price requires cleanup_elected")


def _pro_rata(amount: int, weights: Mapping[str, int]) -> dict[str, int]:
    """Allocate exact cents; use A2a half-up convention for the two A2 tranches."""
    total = sum(weights.values())
    amount = min(amount, total)
    result = dict.fromkeys(weights, 0)
    if not total or not amount:
        return result
    if set(weights) == {"A2a", "A2b"}:
        first = _round(Decimal(amount) * weights["A2a"] / total)
        return {"A2a": first, "A2b": amount - first}
    remainders = []
    for order, (n, w) in enumerate(weights.items()):
        result[n], rem = divmod(amount * w, total)
        remainders.append((-rem, order, n))
    for _, _, n in sorted(remainders)[:amount - sum(result.values())]:
        result[n] += 1
    return result


def distribute_period(state: ScenarioState, period: CollateralPeriod,
                      terms: DealTerms | None = None) -> tuple[ScenarioState, dict[str, Any]]:
    """Distribute one observed/assumed collateral period with independent state.

    ``senior_expenses`` is only qualified capped SSA/indenture clause-2 expense
    cash, with eligibility and aggregate cap checked by the caller. Ordinary
    indenture trustee expenses ``trustee_fee`` are clause-13 claims; on
    acceleration they move to the second tier. Neither is silently inferred.
    Unreimbursed advances, unrelated amounts and successor servicing premiums
    must not be placed in these fields: they require a separately reviewed
    transaction adapter. The adapter's omitted claims are explicitly zero.
    """
    terms = terms or DealTerms()
    prior = date.fromisoformat(state.prior_distribution_date)
    current = date.fromisoformat(period.distribution_date)
    if prior < date.fromisoformat(terms.first_distribution_date):
        raise ValueError("initial issuance stub requires a separately reviewed adapter")
    if current <= prior or current.year * 12 + current.month != prior.year * 12 + prior.month + 1:
        raise ValueError("distribution dates must advance one calendar month")
    pool_difference = state.pool_balance - period.pool_end
    if pool_difference != period.principal_collected + period.defaults + period.repurchases:
        raise ValueError("pool does not conserve principal: begin-end != collections+defaults+repurchases")
    notes = _note_map(state.note_balances, "note_balances")
    monthly_arrears = _note_map(state.interest_arrears, "interest_arrears")
    overdue_arrears = _note_map(state.overdue_interest_arrears, "overdue_interest_arrears")
    interest, monthly_interest, interest_on_arrears = {}, {}, {}
    days = (current - prior).days
    with localcontext() as ctx:
        ctx.prec = 80
        oc_target = _round(Decimal(terms.initial_pool_balance) * _rate(terms.oc_rate, "oc_rate"))
        servicing_due = _round(Decimal(state.pool_balance) * _rate(terms.servicing_rate, "servicing_rate") / 12) + state.servicing_arrears
        for n in NOTES:
            rate = _rate(period.floating_note_rate if n == "A2b" else terms.fixed_rates[n], n)
            fraction = Decimal(days) / 360 if n in ("A1", "A2b") else Decimal(1) / 12
            monthly_interest[n] = _round(Decimal(notes[n]) * rate * fraction)
            interest_on_arrears[n] = _round(Decimal(monthly_arrears[n]) * rate * fraction) if terms.accrue_interest_on_arrears else 0
            interest[n] = monthly_interest[n] + monthly_arrears[n] + overdue_arrears[n] + interest_on_arrears[n]
    trustee_due = period.trustee_fee + state.trustee_arrears
    senior_due = period.senior_expenses + state.senior_expense_arrears
    accelerated = state.accelerated or period.accelerated
    reason = state.acceleration_reason if state.accelerated else period.acceleration_reason
    if accelerated and period.cleanup_elected:
        raise ValueError("cleanup and acceleration cannot be combined without a reviewed legal adapter")
    if period.cleanup_elected:
        if period.pool_end > _round(Decimal(terms.initial_pool_balance) * _rate(terms.cleanup_threshold, "cleanup_threshold")):
            raise ValueError("cleanup threshold not met")
        if period.cleanup_notice_days < 10:
            raise ValueError("cleanup requires at least ten days prior notice")
        price_floor = period.pool_end + period.cleanup_accrued_receivable_interest + period.cleanup_other_property_value
        if period.cleanup_price < price_floor:
            raise ValueError("cleanup price below receivable purchase amount and other property value")
    pool_end = 0 if period.cleanup_elected else period.pool_end
    collections = (period.principal_collected + period.interest_collected + period.recoveries
                   + period.repurchases + period.investment_income + period.cleanup_price)
    reserve_start = state.reserve_balance + period.reserve_interest
    total_notes = sum(notes.values())
    class_a = sum(notes[n] for n in CLASS_A)
    matured_a = sum(notes[n] for n in CLASS_A if current >= date.fromisoformat(terms.final_dates[n]))
    priority = min(total_notes, max(class_a - pool_end, matured_a, 0))
    secondary = max(class_a + notes["B"] - pool_end - priority, 0)
    if current >= date.fromisoformat(terms.final_dates["B"]):
        secondary = max(secondary, notes["B"])
    tertiary = max(class_a + notes["B"] + notes["C"] - pool_end - priority - secondary, 0)
    if current >= date.fromisoformat(terms.final_dates["C"]):
        tertiary = max(tertiary, notes["C"])
    quaternary = max(total_notes - pool_end - priority - secondary - tertiary, 0)
    if current >= date.fromisoformat(terms.final_dates["D"]):
        quaternary = max(quaternary, notes["D"])
    tiers = priority + secondary + tertiary + quaternary
    if tiers > total_notes:
        raise AssertionError("principal tier amounts exceed outstanding notes")
    regular = min(total_notes - tiers, max(total_notes + oc_target - pool_end - tiers, 0))
    required_payment = servicing_due + senior_due + sum(interest.values()) + tiers
    prohibited_fee = servicing_due if terms.affiliated_servicer else 0
    reserve_draw = max(0, min(max(required_payment - collections, 0), reserve_start) - prohibited_fee)
    # SSA 4.1(d): sweep reserve, skip top-up, and pay every note in full.
    payoff_sweep = (not accelerated and collections + reserve_start >= total_notes + sum(interest.values()) + servicing_due + senior_due + trustee_due
                    and collections >= prohibited_fee)
    if accelerated or pool_end == 0 or payoff_sweep:
        reserve_draw = reserve_start
    if period.cleanup_elected and collections + reserve_draw < total_notes + sum(interest.values()) + servicing_due + senior_due + trustee_due:
        raise ValueError("cleanup funds cannot redeem notes and accrued claims in full")
    if period.cleanup_elected and collections < prohibited_fee:
        raise ValueError("cleanup would use reserve for affiliated servicing")
    if payoff_sweep:
        regular = total_notes - tiers
    collection_cash, drawn_cash = collections, reserve_draw
    reserve = reserve_start - reserve_draw
    principal_paid, interest_paid = _zero_notes(), _zero_notes()
    ledger_steps = []

    def pay(amount: int, label: str, allow_reserve: bool = True) -> int:
        nonlocal collection_cash, drawn_cash
        from_collection = min(amount, collection_cash)
        collection_cash -= from_collection
        from_reserve = min(amount - from_collection, drawn_cash) if allow_reserve else 0
        drawn_cash -= from_reserve
        paid = from_collection + from_reserve
        ledger_steps.append({"step": label, "due_cents": amount, "paid_cents": paid,
                             "collection_cents": from_collection, "reserve_cents": from_reserve})
        return paid

    def pay_interest(group: tuple[str, ...], label: str) -> None:
        due = {n: interest[n] - interest_paid[n] for n in group}
        allocation = _pro_rata(pay(sum(due.values()), label), due)
        for n, p in allocation.items():
            interest_paid[n] += p

    def pay_principal(amount: int, label: str, pro_rata_a: bool = False) -> int:
        remaining = sum(notes[n] - principal_paid[n] for n in NOTES)
        paid = pay(min(amount, remaining), label)
        left = paid
        groups = GROUPS
        if pro_rata_a:
            groups = (("A1",), ("A2a", "A2b", "A3", "A4"), ("B",), ("C",), ("D",))
        for group in groups:
            balance = {n: notes[n] - principal_paid[n] for n in group}
            amount_group = min(left, sum(balance.values()))
            if pro_rata_a and len(group) == 4:
                class_weights = {"A2": balance["A2a"] + balance["A2b"], "A3": balance["A3"], "A4": balance["A4"]}
                class_pays = _pro_rata(amount_group, class_weights)
                allocated = _pro_rata(class_pays["A2"], {n: balance[n] for n in ("A2a", "A2b")})
                allocated.update({n: class_pays[n] for n in ("A3", "A4")})
            else:
                allocated = _pro_rata(amount_group, balance)
            for n, p in allocated.items():
                principal_paid[n] += p
            left -= amount_group
        assert left == 0
        return paid

    servicing_paid = pay(servicing_due, "servicing", allow_reserve=not terms.affiliated_servicer)
    senior_paid = 0
    trustee_paid = 0
    reserve_deposit = 0
    extra_principal = 0
    extra_tail = 0
    principal_tier_paid = {}
    if accelerated:
        expense_allocation = _pro_rata(pay(senior_due + trustee_due, "accelerated_second_tier_expenses"),
                                       {"senior": senior_due, "trustee": trustee_due})
        senior_paid = expense_allocation["senior"]
        trustee_paid = expense_allocation["trustee"]
        pay_interest(CLASS_A, "class_A_interest")
        if reason == "covenant_or_representation":
            for n in ("B", "C", "D"):
                pay_interest((n,), f"{n}_interest")
        # A1 first; remaining class-A principal pro rata after acceleration.
        paid_a = pay_principal(sum(notes[n] for n in CLASS_A), "class_A_accelerated_principal", pro_rata_a=True)
        principal_tier_paid["class_A_accelerated"] = paid_a
        for n in ("B", "C", "D"):
            if reason == "payment_or_bankruptcy":
                pay_interest((n,), f"{n}_interest")
            principal_tier_paid[n] = pay_principal(notes[n], f"{n}_accelerated_principal", pro_rata_a=True)
    else:
        senior_paid = pay(senior_due, "qualified_senior_expenses")
        pay_interest(CLASS_A, "class_A_interest")
        principal_tier_paid["priority"] = pay_principal(priority, "priority_principal")
        for n, amount, label in (("B", secondary, "secondary"), ("C", tertiary, "tertiary"), ("D", quaternary, "quaternary")):
            pay_interest((n,), f"{n}_interest")
            principal_tier_paid[label] = pay_principal(amount, f"{label}_principal")
        reserve_required = 0 if pool_end == 0 or payoff_sweep else terms.reserve_minimum
        # A reserve draw is not redeposited as its own top-up.
        reserve_deposit = pay(max(reserve_required - reserve, 0), "reserve_top_up", allow_reserve=False)
        reserve += reserve_deposit
        principal_tier_paid["regular"] = pay_principal(regular, "regular_principal")
        trustee_paid = pay(trustee_due, "ordinary_trustee_tail_expenses")
        # SSA 4.7: excess reserve funds regular principal before tail expenses.
        excess = max(reserve - reserve_required, 0)
        unfunded_regular = max(regular - principal_tier_paid["regular"], 0)
        extra_principal = min(excess, unfunded_regular)
        if extra_principal:
            reserve -= extra_principal
            drawn_cash += extra_principal
            principal_tier_paid["regular"] += pay_principal(extra_principal, "reserve_excess_regular_principal")
        extra_tail = min(max(reserve - reserve_required, 0), trustee_due - trustee_paid)
        if extra_tail:
            reserve -= extra_tail
            drawn_cash += extra_tail
            trustee_paid += pay(extra_tail, "reserve_excess_tail_expenses")
    # Cash withdrawn but not distributable never becomes certificate residual.
    reserve_refund = drawn_cash
    reserve += reserve_refund
    drawn_cash = 0
    note_end = {n: notes[n] - principal_paid[n] for n in NOTES}
    new_monthly_arrears, new_overdue_arrears = {}, {}
    for n in NOTES:
        late_due = overdue_arrears[n] + interest_on_arrears[n]
        paid_late = min(interest_paid[n], late_due)
        new_overdue_arrears[n] = late_due - paid_late
        new_monthly_arrears[n] = monthly_arrears[n] + monthly_interest[n] - (interest_paid[n] - paid_late)
    shortfalls = {n: new_monthly_arrears[n] + new_overdue_arrears[n] for n in NOTES}
    all_notes_paid = not sum(note_end.values()) and not sum(shortfalls.values())
    # Post-acceleration reserve cannot be distributed to certificateholders.
    # Any remainder is retained; the separate trust-termination transfer is
    # outside acceleration cash distributions and is not counted as note cash.
    reserve_required = 0 if pool_end == 0 or payoff_sweep else terms.reserve_minimum
    reserve_release = max(reserve - reserve_required, 0) if not accelerated else 0
    if all_notes_paid and not accelerated:
        reserve_release = reserve
    reserve -= reserve_release
    termination_release = 0
    if period.trust_termination:
        if not all_notes_paid or pool_end != 0:
            raise ValueError("trust termination requires exhausted collateral and all note claims paid")
        # SSA4.7(e): a separate depositor transfer on termination; never
        # certificate residual in the post-acceleration waterfall.
        termination_release = reserve
        reserve = 0
    residual = collection_cash
    maturity_shortfalls = {n: note_end[n] if current >= date.fromisoformat(terms.final_dates[n]) else 0 for n in NOTES}
    cash_uses = servicing_paid + senior_paid + trustee_paid + sum(interest_paid.values()) + sum(principal_paid.values()) + residual + reserve + reserve_release + termination_release
    cash_sources = collections + state.reserve_balance + period.reserve_interest
    if cash_sources != cash_uses:
        raise AssertionError(f"cash conservation failed: {cash_sources} != {cash_uses}")
    new_state = ScenarioState(pool_end, note_end, reserve, period.distribution_date,
                              new_monthly_arrears, new_overdue_arrears,
                              servicing_due - servicing_paid, trustee_due - trustee_paid,
                              senior_due - senior_paid, accelerated, reason)
    result = {
        "distribution_date": period.distribution_date, "month": period.distribution_date[:7],
        "pool_begin": state.pool_balance, "pool_end": pool_end,
        "pool_before_cleanup": period.pool_end, "principal_collected": period.principal_collected,
        "scheduled_principal": period.principal_collected - period.prepayments,
        "prepayments": period.prepayments, "defaults": period.defaults,
        "repurchases": period.repurchases, "recoveries": period.recoveries,
        "interest_collected": period.interest_collected, "available_collections": collections,
        "investment_income": period.investment_income, "cleanup_price": period.cleanup_price,
        "note_begin": notes, "note_end": note_end, "interest_due": interest,
        "monthly_interest": monthly_interest, "interest_on_arrears": interest_on_arrears,
        "interest": interest_paid, "principal": principal_paid, "interest_shortfalls": shortfalls,
        "maturity_shortfalls": maturity_shortfalls, "servicing_due": servicing_due,
        "servicing_paid": servicing_paid, "servicing_shortfall": new_state.servicing_arrears,
        "senior_expenses_paid": senior_paid, "trustee_paid": trustee_paid,
        "reserve_begin": state.reserve_balance, "reserve_interest": period.reserve_interest,
        "reserve_draw": reserve_draw, "reserve_draw_refunded": reserve_refund,
        "reserve_deposit": reserve_deposit, "reserve_release": reserve_release, "reserve_end": reserve,
        "reserve_excess_principal": extra_principal, "reserve_excess_tail_expenses": extra_tail,
        "reserve_termination_release": termination_release,
        "residual_distribution": residual, "principal_tier_due": {"priority": priority,
            "secondary": secondary, "tertiary": tertiary, "quaternary": quaternary, "regular": regular},
        "principal_tier_paid": principal_tier_paid, "oc_target": oc_target,
        "payoff_sweep": payoff_sweep, "accelerated": accelerated, "acceleration_reason": reason,
        "cleanup_elected": period.cleanup_elected, "all_notes_paid": all_notes_paid,
        "ledger_steps": ledger_steps, "checks": {"cash_sources_cents": cash_sources,
            "cash_uses_cents": cash_uses, "cash_conservation": cash_sources == cash_uses,
            "principal_conservation": total_notes == sum(principal_paid.values()) + sum(note_end.values()),
            "pool_conservation": pool_difference == period.principal_collected + period.defaults + period.repurchases,
            "reserve_conservation": (reserve_start + reserve_deposit == reserve + reserve_draw - reserve_refund
                                      + extra_principal + extra_tail + reserve_release + termination_release),
            "affiliate_servicing_reserve_cents": next(x["reserve_cents"] for x in ledger_steps if x["step"] == "servicing") if terms.affiliated_servicer else 0},
    }
    return new_state, result


def run_scenario(initial_state: ScenarioState, periods: Iterable[CollateralPeriod],
                 terms: DealTerms | None = None, *, terminal: bool = True) -> dict[str, Any]:
    """Run supplied future periods and report paid-principal WAL and losses.

    ``terminal=True`` declares that the caller has included all future recovery
    cash. A nonzero ending pool still fails horizon closure. Economic terminal
    losses are reported separately from contractual liability balances.
    WAL uses principal actually repaid as denominator, with its recovered
    fraction disclosed. Full contractual WAL is unavailable for impaired or
    incomplete notes; no terminal loss is counted as a principal payment.
    """
    terms = terms or DealTerms()
    state = initial_state
    monthly = []
    for p in periods:
        state, row = distribute_period(state, p, terms)
        monthly.append(row)
    if not monthly:
        raise ValueError("at least one period is required")
    runoff_complete = terminal and state.pool_balance == 0 and state.reserve_balance == 0
    origin = date.fromisoformat(initial_state.prior_distribution_date)
    tranches = []
    for n in NOTES:
        opening = initial_state.note_balances[n]
        principal = sum(r["principal"][n] for r in monthly)
        interest = sum(r["interest"][n] for r in monthly)
        loss = state.note_balances[n] if runoff_complete else 0
        shortfall = state.interest_arrears[n] + state.overdue_interest_arrears[n]
        weighted_days = sum(r["principal"][n] * (date.fromisoformat(r["distribution_date"]) - origin).days for r in monthly)
        paid_wal = weighted_days / principal / 365.25 if principal else None
        wal = paid_wal if loss == 0 and state.note_balances[n] == 0 else None
        rows = [{"month": r["month"], "distribution_date": r["distribution_date"],
                 "opening_balance_cents": r["note_begin"][n], "interest_paid_cents": r["interest"][n],
                 "principal_paid_cents": r["principal"][n], "closing_balance_cents": r["note_end"][n],
                 "interest_shortfall_cents": r["interest_shortfalls"][n],
                 "maturity_shortfall_cents": r["maturity_shortfalls"][n], "loss_cents": 0} for r in monthly]
        if loss:
            rows[-1]["loss_cents"] = loss
            rows[-1]["economic_closing_balance_cents"] = 0
        tranches.append({"name": n, "opening_balance_cents": opening,
                         "principal_paid_cents": principal, "interest_paid_cents": interest,
                         "loss_cents": loss, "interest_shortfall_cents": shortfall,
                         "contractual_remaining_balance_cents": state.note_balances[n],
                         "wal_years": wal, "repaid_principal_wal_years": paid_wal,
                         "principal_recovery_fraction": principal / opening if opening else None,
                         "maturity_failure": any(r["maturity_shortfalls"][n] > 0 for r in monthly),
                         "rows": rows})
    return {"monthly": monthly, "tranches": tranches, "final_state": asdict(state),
            "checks": {"cash_conservation": all(r["checks"]["cash_conservation"] for r in monthly),
                       "principal_conservation": all(r["checks"]["principal_conservation"] for r in monthly),
                       "pool_conservation": all(r["checks"]["pool_conservation"] for r in monthly),
                       "reserve_conservation": all(r["checks"]["reserve_conservation"] for r in monthly),
                       "horizon_closed": runoff_complete,
                       "future_recoveries_declared_complete": terminal,
                       "terminal_principal_losses_cents": sum(t["loss_cents"] for t in tranches),
                       "unresolved_principal_cents": 0 if runoff_complete else sum(state.note_balances.values()),
                       "maturity_failures": [t["name"] for t in tranches if t["maturity_failure"]]},
            "legal_sources": {"sale_servicing": SSA_URL, "indenture": INDENTURE_URL},
            "limits": ["Floating coupons and collateral cash are supplied scenario inputs.",
                       "Acceleration and optional purchase elections are explicit, not inferred.",
                       "Unreimbursed advances, unrelated amounts, successor premiums and unclassified fees are zero.",
                       "Interest on arrears is conditional on the documented lawful-interest assumption.",
                       "Terminal losses are economic scenario impairment, not an executed legal writeoff."]}


def reverse_stress(scenario_factory: Callable[[Decimal], dict[str, Any]],
                   severities: Iterable[str | Decimal], *, tranche: str = "D") -> dict[str, Any]:
    """Evaluate every specified joint-shock grid point without monotonicity claims.

    A breach is terminal principal loss, unpaid interest or a legal-maturity
    failure for the selected tranche. Nonclosed scenario horizons are reported
    separately and cannot establish a safe point.
    """
    if tranche not in NOTES:
        raise ValueError("unknown tranche")
    rows = []
    preceding_severity = None
    for value in severities:
        if not isinstance(value, (str, Decimal)):
            raise ValueError("severity must be a decimal string or Decimal")
        severity = Decimal(value)
        if not severity.is_finite() or severity < 0:
            raise ValueError("severity must be finite and nonnegative")
        if preceding_severity is not None and severity <= preceding_severity:
            raise ValueError("reverse-stress severity grid must increase strictly")
        preceding_severity = severity
        scenario = scenario_factory(severity)
        t = next(t for t in scenario["tranches"] if t["name"] == tranche)
        closed = scenario["checks"]["horizon_closed"]
        breached = bool(t["loss_cents"] or t["interest_shortfall_cents"] or t["maturity_failure"])
        rows.append({"severity": str(severity), "breach": breached,
                     "horizon_closed": closed, "principal_loss_cents": t["loss_cents"],
                     "interest_shortfall_cents": t["interest_shortfall_cents"],
                     "maturity_failure": t["maturity_failure"]})
    if not rows:
        raise ValueError("reverse stress requires a nonempty severity grid")
    first = next((i for i, r in enumerate(rows) if r["breach"]), None)
    preceding = rows[first - 1] if first is not None and first > 0 else None
    return {"tranche": tranche, "grid": rows,
            "first_breach": rows[first] if first is not None else None,
            "preceding_safe": preceding if preceding and not preceding["breach"] and preceding["horizon_closed"] else None,
            "all_horizons_closed": all(r["horizon_closed"] for r in rows),
            "interpretation": "First observed breach on the supplied ordered grid; not a continuous or multidimensional minimum."}
