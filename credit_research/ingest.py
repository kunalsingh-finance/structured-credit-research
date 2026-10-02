"""Source-faithful SEC auto-ABS ingestion, with bounded-memory XML parsing.

Money is integer cents. Omitted fields remain None. Credit scores may be decimal
averages for co-obligors; NONE is missing, not a zero score. XML percentages are
fractions (0.0814), normalized percentage columns use percentage points (8.14).
The raw tape charge-off and recovery amounts are retained separately from first
default labels. SEC acceptance time describes public availability, not period end.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
from html.parser import HTMLParser
from functools import lru_cache
from pathlib import Path
import re
import xml.etree.ElementTree as ET

AUTO_NAMESPACE = "http://www.sec.gov/edgar/document/absee/autoloan/assetdata"
NOTES = ("A1", "A2a", "A2b", "A3", "A4", "B", "C", "D")


def money_cents(value, *, signed=False):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", value):
        raise ValueError(f"Invalid exact-cent amount {value!r}")
    result = int(Decimal(value) * 100)
    if result < 0 and not signed:
        raise ValueError("Negative magnitude is not supported")
    return result


def numeric(value):
    if value in (None, "", "NONE"):
        return None
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid numeric value {value!r}") from error
    if not result.is_finite():
        raise ValueError("Non-finite numeric value")
    return float(result)


def integer(value):
    result = numeric(value)
    if result is None:
        return None
    if result != int(result):
        raise ValueError("Non-integral count")
    return int(result)


@lru_cache(maxsize=1024)
def xml_date(value):
    if value is None:
        return None
    return datetime.strptime(value, "%m-%d-%Y").date().isoformat()


@lru_cache(maxsize=1024)
def month_date(value):
    return datetime.strptime(value, "%m/%Y").date() if value else None


@lru_cache(maxsize=1024)
def validate_month_interval(period_start, period_end):
    start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
    if start.day != 1 or start.replace(day=calendar.monthrange(start.year, start.month)[1]) != end:
        raise ValueError("Tape record does not span exactly one calendar month")
    return start


def open_archive(path: Path):
    return gzip.open(path, "rb") if str(path).endswith(".gz") else path.open("rb")


def verify_archive(path: Path, metadata: dict):
    """Verify both compressed archive and original uncompressed bytes."""
    archive_hash = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            archive_hash.update(block)
    if archive_hash.hexdigest() != metadata["sha256_archive"]:
        raise ValueError(f"Archive SHA-256 mismatch: {path}")
    original_hash = hashlib.sha256()
    count = 0
    with open_archive(path) as stream:
        while block := stream.read(1024 * 1024):
            original_hash.update(block)
            count += len(block)
    if original_hash.hexdigest() != metadata["sha256_original_bytes"] or count != metadata["original_byte_count"]:
        raise ValueError(f"Original-byte SHA-256/size mismatch: {path}")


def iter_auto_assets(path: Path):
    """Yield one raw record at a time; reject namespace drift and duplicate keys.

The actual EDGAR XSD root is assetData with repeated assets elements. Clearing
the root after every record prevents ElementTree from retaining empty siblings.
Duplicate loan IDs are detected within each source's reported month.
"""
    with open_archive(path) as stream:
        events = ET.iterparse(stream, events=("start", "end"))
        try:
            _, root = next(events)
        except StopIteration as error:
            raise ValueError("Empty XML") from error
        if root.tag != "{" + AUTO_NAMESPACE + "}assetData":
            raise ValueError(f"Unexpected SEC asset-data namespace/root: {root.tag}")
        seen = set()
        for event, element in events:
            if event == "end" and element.tag == "{" + AUTO_NAMESPACE + "}assets":
                fields = {}
                for child in element:
                    if not child.tag.startswith("{" + AUTO_NAMESPACE + "}"):
                        raise ValueError("Unexpected field namespace")
                    key = child.tag.split("}", 1)[1]
                    if key in fields:
                        if key not in {"modificationTypeCode", "zeroBalanceCode", "subvented", "repurchaseReplacementReasonCode"}:
                            raise ValueError(f"Duplicate XML field {key}")
                        previous = fields[key] if isinstance(fields[key], list) else [fields[key]]
                        fields[key] = previous + [child.text]
                    else:
                        fields[key] = child.text
                identity = (fields.get("assetNumber"), fields.get("reportingPeriodEndingDate"))
                if not identity[0] or identity in seen:
                    raise ValueError(f"Missing or duplicate loan-period identifier: {identity}")
                seen.add(identity)
                yield fields
                element.clear()
                root.clear()


MONEY_MAP = {
    "original_balance_cents": "originalLoanAmount",
    "begin_balance_cents": "reportingPeriodBeginningLoanBalanceAmount",
    "end_balance_cents": "reportingPeriodActualEndBalanceAmount",
    "scheduled_payment_cents": "reportingPeriodScheduledPaymentAmount",
    "scheduled_principal_cents": "scheduledPrincipalAmount",
    "principal_paid_cents": "actualPrincipalCollectedAmount",
    "interest_paid_cents": "actualInterestCollectedAmount",
    "other_principal_adjustment_cents": "otherPrincipalAdjustmentAmount",
    "chargeoff_cents": "chargedoffPrincipalAmount",
    "recovery_cents": "recoveredAmount",
    "repurchase_cents": "repurchaseAmount",
    "vehicle_value_cents": "vehicleValueAmount",
}


def normalize_asset(raw: dict, source: dict):
    period_start = xml_date(raw.get("reportingPeriodBeginningDate"))
    period_end = xml_date(raw.get("reportingPeriodEndingDate"))
    if not period_start or not period_end or period_end != source["report_period"]:
        raise ValueError("Tape reporting date differs from its filing metadata")
    start = validate_month_interval(period_start, period_end)
    row = {"deal_id": source["deal_id"], "loan_id": raw["assetNumber"],
        "period_start": period_start, "period_end": period_end,
        "acceptance_time": source["acceptance_time"], "accession": source["accession"]}
    for output, field in MONEY_MAP.items():
        # SEC decimal fields permit signed numbers. Actual servicing tapes have
        # small credit balances and negative scheduled/principal amounts; retain
        # these source facts rather than clamping them during normalization.
        row[output] = money_cents(raw.get(field), signed=True)
    for key in ("original_balance_cents", "begin_balance_cents", "end_balance_cents", "principal_paid_cents", "interest_paid_cents"):
        if row[key] is None:
            raise ValueError(f"Required core tape field omitted: {key}")
    origination = raw.get("originationDate")
    orig = month_date(origination)
    row["origination_month"] = f"{orig.year:04}-{orig.month:02}" if orig else None
    row["age_months"] = (start.year - orig.year) * 12 + start.month - orig.month if orig else None
    row["remaining_months"] = integer(raw.get("remainingTermToMaturityNumber"))
    row["original_term_months"] = integer(raw.get("originalLoanTerm"))
    maturity = month_date(raw.get("loanMaturityDate"))
    row["maturity_month"] = f"{maturity.year:04}-{maturity.month:02}" if maturity else None
    row["credit_score"] = numeric(raw.get("obligorCreditScore"))
    row["delinquency_days"] = integer(raw.get("currentDelinquencyStatus"))
    row["interest_rate_pct"] = None if raw.get("reportingPeriodInterestRatePercentage") is None else numeric(raw["reportingPeriodInterestRatePercentage"]) * 100
    row["orig_ltv_pct"] = (row["original_balance_cents"] / row["vehicle_value_cents"] * 100) if row["vehicle_value_cents"] else None
    row["payment_to_income_pct"] = None if raw.get("paymentToIncomePercentage") is None else numeric(raw["paymentToIncomePercentage"]) * 100
    row["state"] = raw.get("obligorGeographicLocation")
    codes = raw.get("zeroBalanceCode")
    row["zero_balance_code"] = "|".join(codes) if isinstance(codes, list) else codes
    zero = month_date(raw.get("zeroBalanceEffectiveDate"))
    row["zero_balance_month"] = f"{zero.year:04}-{zero.month:02}" if zero else None
    row["liquidation_date"] = None  # zero-balance effective month is not an exact collateral liquidation date.
    row["status_code"] = row["zero_balance_code"] or "ACTIVE"
    row["repossessed"] = None if raw.get("repossessedIndicator") is None else int(raw["repossessedIndicator"] == "true")
    row["modified"] = None if raw.get("reportingPeriodModificationIndicator") is None else int(raw["reportingPeriodModificationIndicator"] == "true")
    row["first_default_event"] = 0  # filled after all versions are inserted, once per loan.
    row["prepayment_event"] = 0
    row["repurchase_event"] = 0
    row["maturity_event"] = 0
    row["prepayment_cents"] = None
    return row


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def dollar_string(cents):
    return f"{Decimal(cents) / 100:.2f}"


def parse_certificate_html(content: bytes, source: dict, prior_distribution_date: str):
    parser = TableRows()
    parser.feed(content.decode("utf-8"))
    rows = {}
    section = None
    for cells in parser.rows:
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        if re.fullmatch(r"\d+\.", nonempty[0]):
            section = nonempty[0][:-1]
            key = section
        elif section and re.match(r"^[a-z]\.\s", nonempty[0]):
            key = section + nonempty[0][0]
        else:
            continue
        values = []
        for index, cell in enumerate(cells):
            if cell == "$":
                amount = next((c for c in cells[index + 1:] if c), None)
                if amount is None:
                    raise ValueError(f"Missing dollar cell at source row {key}")
                # A few 2024-2 retired A2 interest cells contain an actual U+FFFD
                # source character. Preserve missingness; never silently turn it
                # into zero or pretend its value was reported.
                values.append(None if amount in {"�", "—", "–", "-"} else money_cents(amount.replace(",", ""), signed=True))
        rows.setdefault(key, {"label": " | ".join(nonempty), "money_cents": values})
    def amount(key, index=0):
        if key not in rows or len(rows[key]["money_cents"]) <= index or rows[key]["money_cents"][index] is None:
            raise ValueError(f"Missing expected certificate source row {key}")
        return rows[key]["money_cents"][index]
    def total(keys):
        return sum(amount(k) for k in keys)
    simple = {"pool_begin": "1", "principal_collected": "2", "repurchases": "3", "defaults": "4", "pool_end": "5",
        "interest_collected": "17a", "recoveries": "77", "investment_income": "20", "available_collections": "23",
        "reserve_draw": "24", "servicing_fee": "26c", "reserve_deposit": "44d", "residual_distribution": "44e",
        "total_distributions": "44f", "reserve_begin": "50", "reserve_interest": "51", "reserve_end": "57",
        "gross_loss": "76", "net_loss": "78"}
    amounts = {key: dollar_string(amount(row)) for key, row in simple.items()}
    interest_rows = ["45" + c for c in "abcdefgh"]
    missing_interest = [key for key in interest_rows if rows[key]["money_cents"][0] is None]
    principal_total = total(["45" + c for c in "ijklmnop"])
    interest_total = amount("45q") - principal_total if missing_interest else total(interest_rows)
    amounts.update(note_begin=dollar_string(amount("8i")), note_end=dollar_string(amount("8i", 1)),
        trustee_fee=dollar_string(total(["28b", "28e", "41a", "41b"])),
        total_note_interest=dollar_string(interest_total),
        total_note_principal=dollar_string(principal_total),
        reserve_release=dollar_string(total(["55a", "55b", "56"])))
    period = source["report_period"]
    collection_start = period[:8] + "01"
    header = {cells[0]: next((c for c in cells[1:] if c), None) for cells in parser.rows
              if cells and cells[0] in {"Collection Period", "Determination Date", "Distribution Date"}}
    distribution_row = next(c for c in parser.rows if c and c[0] == "Distribution Date")
    reported_distribution = datetime.strptime(next(c for c in distribution_row[1:] if c), "%m/%d/%Y").date().isoformat()
    document_date = re.search(r"ex991(\d{6})\.htm", source["url"])
    distribution = datetime.strptime(document_date[1], "%m%d%y").date().isoformat() if document_date else reported_distribution
    date_exception = [] if distribution == reported_distribution else [
        f"Header reports Distribution Date {reported_distribution}; exhibit filename identifies {distribution}. "
        "Both values retained; filename date is used for chronology and remains an explicit source-label exception."]
    reported_collection = header.get("Collection Period")
    if reported_collection:
        stated_start, stated_end = reported_collection.split("-")
        stated_start = datetime.strptime(stated_start, "%m/%d/%y").date().isoformat()
        stated_end = datetime.strptime(stated_end, "%m/%d/%y").date().isoformat()
        if (stated_start, stated_end) != (collection_start, period):
            date_exception.append(f"Header collection period {reported_collection} differs from actual SEC 10-D report period {period}; "
                                  "source header retained, SEC submission report-period metadata used.")
    interest = {note: dollar_string(amount("45" + c)) for note, c in zip(NOTES, "abcdefgh") if "45" + c not in missing_interest}
    principal = {note: dollar_string(amount("45" + c)) for note, c in zip(NOTES, "ijklmnop")}
    ending = {note: dollar_string(amount("8" + c, 1)) for note, c in zip(NOTES, "abcdefgh")}
    beginning = {note: dollar_string(amount("8" + c)) for note, c in zip(NOTES, "abcdefgh")}
    numeric_cells = [c.replace(",", "") for c in next(c for c in parser.rows if c and c[0] == "16.")
                     if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", c.replace(",", ""))]
    floating_rate = str(Decimal(numeric_cells[-1]) / 100) if numeric_cells else None
    count_row = next(c for c in parser.rows if c and c[0] == "6.")
    count = int(next(c for c in reversed(count_row) if re.fullmatch(r"[0-9,]+", c)).replace(",", ""))
    return {"deal_id": source["deal_id"], "collection_period_start": collection_start,
        "collection_period_end": period, "distribution_date": distribution,
        "source_reported_distribution_date": reported_distribution,
        "distribution_date_method": "Dated SEC exhibit filename; independently visible header retained",
        "collection_period_method": "SEC actual 10-D report-period metadata; complete calendar month",
        "source_header": header,
        "acceptance_time": source["acceptance_time"], "accession": source["accession"],
        "source_url": source["url"], "source_sha256": source["sha256_original_bytes"],
        "extraction_method": "Automated numbered-row extraction from archived original SEC EX-99.1 HTML; exact cents",
        "outstanding_loan_count": count, "amounts": amounts,
        "replay_inputs": {**{k: amounts[k] for k in ("pool_begin", "pool_end", "available_collections", "reserve_begin", "reserve_interest")},
            "prior_distribution_date": prior_distribution_date, "distribution_date": distribution,
            "floating_note_rate": floating_rate, "note_begin": beginning},
        "expected": {"interest": interest, "principal": principal, "note_end": ending,
            **{name: dollar_string(amount(row)) for name, row in {"priority_principal": "30", "secondary_principal": "32",
                 "tertiary_principal": "34", "quaternary_principal": "36", "regular_principal": "39", "reported_oc_target": "10"}.items()}},
        "source_field_map": {**simple, "note_begin": "8i beginning", "note_end": "8i ending",
            "total_note_interest": "45q minus 45i:p (missing retired-note interest cells)" if missing_interest else "45a:h",
            "total_note_principal": "45i:p", "reserve_release": "55a+55b+56"},
        "missing_reported_interest_classes": [n for n, c in zip(NOTES, "abcdefgh") if "45" + c in missing_interest],
        "source_rows": rows,
        "additional_cash_components": {"finance_charge_repurchases": dollar_string(amount("17c")),
            "advances": dollar_string(amount("21")), "unreimbursed_advances": dollar_string(amount("27")),
            "finance_charge_liquidation_receipts": dollar_string(amount("17b")),
            "principal_liquidation_receipts": dollar_string(amount("18b"))},
        "source_exceptions": date_exception + ["Certificate rate-date and percentage labels require independent comparison with executed agreements; numeric amounts are preserved."]}
