import asyncio
import re

from copy import deepcopy

from google import genai
from google.genai import types

from pydantic import BaseModel

from backend.app.core.config import settings

from backend.app.schemas.document import (
    DocumentType,
)

from backend.app.schemas.extraction import (
    InvoiceExtraction,
    BalanceSheetExtraction,
    ProfitAndLossExtraction,
    CashFlowExtraction,
)


# ==========================================================
# EXCEPTIONS
# ==========================================================


class ExtractionError(Exception):
    pass


# ==========================================================
# SYSTEM PROMPT
# ==========================================================


SYSTEM_PROMPT = """
You are a financial document extraction engine.

Your job is to convert OCR/document text into accurate,
structured data.

STRICT RULES:

1. Extract only information supported by the document.
2. Never invent, estimate, infer, repair, or guess values.
3. Never perform financial calculations during extraction.
4. Do not change a number merely because another number
   appears mathematically inconsistent.
5. Preserve negative values.
6. Parentheses around numbers mean negative values when
   clearly used as financial notation.
7. A dash "-" should normally become null rather than zero.
8. Missing or unreadable values must be null.
9. Preserve comparative reporting periods.
10. Extract ALL meaningful visible information, not only
    the minimum fields.
11. Preserve tables and line items.
12. Provide evidence using source text and page number.
13. Do not correct OCR currency symbols unless the source
    explicitly supports the correction.
14. Financial validation will be performed separately by
    deterministic Python code.
"""


# ==========================================================
# LABEL NORMALIZATION
# ==========================================================


def normalize_label(
    value: str | None,
):
    if not value:
        return ""

    text = str(value).strip().lower()

    text = text.replace(
        "&",
        " and ",
    )

    text = text.replace(
        "_",
        " ",
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def normalize_period_key(value):
    """Normalize equivalent comparative-period labels."""

    if value is None:
        return ""

    text = str(value).strip().lower()
    text = text.replace("–", "-").replace("—", "-")

    month_numbers = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    month_number = None

    for month_name, number in month_numbers.items():
        if re.search(
            rf"\b{month_name}[a-z]*\b",
            text,
        ):
            month_number = number
            break

    if month_number is not None:
        year_matches = re.findall(
            r"\b(?:19|20)\d{2}\b|\b\d{2}\b",
            text,
        )

        if year_matches:
            raw_year = year_matches[-1]
            year = int(raw_year)

            if len(raw_year) == 2:
                year += (
                    2000
                    if year < 70
                    else 1900
                )

            return (
                f"{year:04d}-"
                f"{month_number:02d}"
            )

    text = re.sub(
        r"\b("
        r"for\s+the\s+year\s+ended"
        r"|year\s+ended"
        r"|as\s+at"
        r")\b",
        " ",
        text,
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


# ==========================================================
# COMMON NORMALIZATION HELPER
# ==========================================================


def copy_line_item_to_field(
    data: dict,
    target_field: str,
    aliases: set[str],
):
    """
    Copy an explicitly extracted line-item row into a
    dedicated field when the dedicated field is empty.

    This does NOT invent a value.
    """

    existing = data.get(
        target_field,
        [],
    )

    if existing:
        return

    normalized_aliases = {
        normalize_label(
            alias
        )
        for alias in aliases
    }

    for item in data.get(
        "line_items",
        [],
    ):

        name = normalize_label(
            item.get(
                "name"
            )
        )

        if name in normalized_aliases:

            data[
                target_field
            ] = deepcopy(
                item.get(
                    "amounts",
                    [],
                )
            )

            return


# ==========================================================
# INVOICE NORMALIZATION
# ==========================================================


def parse_visible_numeric_value(
    value,
):
    """
    Convert an explicitly extracted textual number into
    numeric form.

    This function does not infer missing values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    text = str(
        value
    ).strip()

    if not text:
        return None

    negative_parentheses = (
        text.startswith("(")
        and text.endswith(")")
    )

    cleaned = (
        text
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("RM", "")
        .strip()
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        cleaned,
    )

    if not match:
        return None

    try:
        result = float(
            match.group()
        )

        if (
            negative_parentheses
            and result > 0
        ):
            result = -result

        return result

    except ValueError:
        return None


def normalize_invoice_data(
    data: dict,
):
    """
    Promote source-backed invoice fields from
    additional_fields into dedicated fields.

    Also distinguish a receipt-style amount before rounding
    from a true subtotal where enough explicit evidence is
    available.
    """

    additional_fields = (
        data.get(
            "additional_fields",
            [],
        )
        or []
    )

    alias_map = {
        "round_off": {
            "round off",
            "rounding adjustment",
            "rounding adj",
            "round off adjustment",
            "rounding",
        },

        "cash_paid": {
            "cash paid",
            "cash tendered",
            "cash",
            "amount tendered",
            "cash received",
        },

        "change": {
            "change",
            "change due",
        },

        "taxable_amount": {
            "taxable amount",
            "taxable value",
            "taxable total",
        },

        "amount_before_rounding": {
            "amount before rounding",
            "total before rounding",
            "pre rounding total",
            "pre-rounding total",
        },
    }

    for (
        target_field,
        aliases,
    ) in alias_map.items():

        current = data.get(
            target_field
        )

        if (
            isinstance(
                current,
                dict,
            )
            and current.get(
                "value"
            ) is not None
        ):
            continue

        normalized_aliases = {
            normalize_label(
                alias
            )
            for alias in aliases
        }

        for extra in additional_fields:

            extra_name = (
                normalize_label(
                    extra.get(
                        "name"
                    )
                )
            )

            if (
                extra_name
                not in normalized_aliases
            ):
                continue

            numeric_value = (
                parse_visible_numeric_value(
                    extra.get(
                        "value"
                    )
                )
            )

            if numeric_value is None:
                continue

            data[
                target_field
            ] = {
                "value": numeric_value,
                "evidence": deepcopy(
                    extra.get(
                        "evidence"
                    )
                ),
            }

            break

    subtotal_field = (
        data.get(
            "subtotal"
        )
        or {}
    )

    before_rounding_field = (
        data.get(
            "amount_before_rounding"
        )
        or {}
    )

    round_off_field = (
        data.get(
            "round_off"
        )
        or {}
    )

    total_field = (
        data.get(
            "total_amount"
        )
        or {}
    )

    subtotal_value = (
        parse_visible_numeric_value(
            subtotal_field.get(
                "value"
            )
        )
    )

    round_off_value = (
        parse_visible_numeric_value(
            round_off_field.get(
                "value"
            )
        )
    )

    total_value = (
        parse_visible_numeric_value(
            total_field.get(
                "value"
            )
        )
    )

    before_rounding_value = (
        parse_visible_numeric_value(
            before_rounding_field.get(
                "value"
            )
        )
    )

    subtotal_evidence = (
        subtotal_field.get(
            "evidence"
        )
        or {}
    )

    subtotal_source = (
        normalize_label(
            subtotal_evidence.get(
                "source_text"
            )
        )
    )

    looks_like_total_amount = (
        "total amt" in subtotal_source
        or "total amount" in subtotal_source
    )

    explicitly_subtotal = (
        "subtotal" in subtotal_source
        or "sub total" in subtotal_source
    )

    if (
        before_rounding_value is None
        and subtotal_value is not None
        and round_off_value is not None
        and total_value is not None
        and looks_like_total_amount
        and not explicitly_subtotal
        and abs(
            (
                subtotal_value
                + round_off_value
            )
            - total_value
        ) <= 0.01
    ):

        data[
            "amount_before_rounding"
        ] = deepcopy(
            subtotal_field
        )

        data[
            "subtotal"
        ] = {
            "value": None,
            "evidence": None,
        }

    return data


# ==========================================================
# BALANCE SHEET NORMALIZATION
# ==========================================================


def _numeric_key(
    value,
):
    """
    Stable comparison key for source-backed numeric values.
    """

    parsed = (
        parse_visible_numeric_value(
            value
        )
    )

    if parsed is None:
        return None

    return round(
        float(parsed),
        6,
    )


def _extract_matching_number_tokens(
    text: str,
    allowed_values: set[float],
):
    """
    Return numeric tokens from source text whose values are
    already present in the extracted Balance Sheet data.

    Kept as a utility for source-backed comparisons.
    """

    tokens = []

    pattern = re.compile(
        r"\(?-?\d[\d,]*(?:\.\d+)?\)?"
    )

    for match in pattern.finditer(
        text
    ):

        raw = match.group(
            0
        )

        key = _numeric_key(
            raw
        )

        if (
            key is not None
            and key in allowed_values
        ):

            parsed_value = (
                parse_visible_numeric_value(
                    raw
                )
            )

            if (
                isinstance(
                    parsed_value,
                    float,
                )
                and parsed_value.is_integer()
            ):
                parsed_value = int(
                    parsed_value
                )

            tokens.append(
                {
                    "raw": raw,
                    "value": parsed_value,
                }
            )

    return tokens


def _extract_source_number_tokens(
    text: str,
):
    """
    Return all explicit numeric tokens from the cropped
    Balance Sheet source area in their original OCR order.

    This deliberately does not require Gemini to have
    extracted every number first.

    Reported Total Assets values are later used as anchors,
    so values remain source-grounded rather than inferred.
    """

    tokens = []

    pattern = re.compile(
        r"\(?-?\d[\d,]*(?:\.\d+)?\)?"
    )

    for match in pattern.finditer(
        text
    ):

        raw = match.group(
            0
        )

        parsed_value = (
            parse_visible_numeric_value(
                raw
            )
        )

        if parsed_value is None:
            continue

        if (
            isinstance(
                parsed_value,
                float,
            )
            and parsed_value.is_integer()
        ):
            parsed_value = int(
                parsed_value
            )

        tokens.append(
            {
                "raw": raw,
                "value": parsed_value,
            }
        )

    return tokens


def _set_period_amount_from_source(
    item: dict,
    period: str,
    token: dict,
):
    """
    Replace only an already-existing period amount using an
    explicit numeric token found in the source document.
    """

    for amount in (
        item.get(
            "amounts",
            [],
        )
        or []
    ):

        if (
            normalize_period_key(
                amount.get(
                    "period"
                )
            )
            != normalize_period_key(
                period
            )
        ):
            continue

        amount[
            "value"
        ] = token[
            "value"
        ]

        evidence = (
            amount.get(
                "evidence"
            )
            or {}
        )

        evidence[
            "source_text"
        ] = token[
            "raw"
        ]

        amount[
            "evidence"
        ] = evidence

        return


def normalize_balance_sheet_data(
    data: dict,
    document_text: str,
):
    """
    Normalize Balance Sheet table alignment without
    inventing values.

    OCR frequently flattens comparative Balance Sheet
    columns. A common layout is:

        asset rows
        Total
        off-balance-sheet rows

    followed by the same values for the comparative period.

    If Gemini shifts a comparative-period value by one row,
    this function rebuilds the mapping from the original OCR
    number sequence, using explicitly extracted Total Assets
    values as source anchors.

    No arithmetic is used to force a balance.
    """

    line_items = (
        data.get(
            "line_items",
            [],
        )
        or []
    )

    periods = (
        data.get(
            "periods",
            [],
        )
        or []
    )

    total_assets = (
        data.get(
            "total_assets",
            [],
        )
        or []
    )

    if (
        len(periods) < 2
        or not line_items
        or len(total_assets) < 2
    ):
        return data

    off_balance_aliases = {
        "contingent liabilities",
        "bills for collection",
    }

    total_aliases = {
        "total",
        "total assets",
        "assets total",
    }

    asset_items = []

    for item in line_items:

        section = normalize_label(
            item.get(
                "section"
            )
        )

        name = normalize_label(
            item.get(
                "name"
            )
        )

        if (
            section == "assets"
            or name in off_balance_aliases
        ):
            asset_items.append(
                item
            )

    if not asset_items:
        return data

    component_items = []
    off_balance_items = []

    for item in asset_items:

        name = normalize_label(
            item.get(
                "name"
            )
        )

        if name in off_balance_aliases:

            item[
                "section"
            ] = "OFF BALANCE SHEET"

            off_balance_items.append(
                item
            )

        elif (
            name not in total_aliases
        ):

            component_items.append(
                item
            )

    component_count = len(
        component_items
    )

    off_balance_count = len(
        off_balance_items
    )

    if (
        component_count == 0
        or off_balance_count == 0
    ):
        return data

    total_by_period = {
        normalize_period_key(
            entry.get(
                "period"
            )
        ): entry.get(
            "value"
        )
        for entry in total_assets
        if entry.get(
            "period"
        ) is not None
    }

    ordered_periods = [
        period
        for period in periods
        if normalize_period_key(
            period
        ) in total_by_period
    ]

    if len(
        ordered_periods
    ) < 2:
        return data

    upper_text = (
        document_text.upper()
    )

    start_index = (
        upper_text.find(
            "\nASSETS\n"
        )
    )

    if start_index < 0:
        start_index = (
            upper_text.find(
                "ASSETS"
            )
        )

    if start_index < 0:
        return data

    end_candidates = []

    for marker in (
        "\nSIGNIFICANT ACCOUNTING",
        "\nTHE SCHEDULES REFERRED",
        "\nAS PER OUR REPORT",
    ):

        found = upper_text.find(
            marker,
            start_index,
        )

        if found >= 0:
            end_candidates.append(
                found
            )

    if end_candidates:
        end_index = min(
            end_candidates
        )
    else:
        end_index = len(
            document_text
        )

    assets_source = (
        document_text[
            start_index:end_index
        ]
    )

    source_tokens = (
        _extract_source_number_tokens(
            assets_source
        )
    )

    if not source_tokens:
        return data

    total_positions = []

    cursor = 0

    for period in ordered_periods:

        total_key = _numeric_key(
            total_by_period.get(
                normalize_period_key(
                    period
                )
            )
        )

        position = None

        for index in range(
            cursor,
            len(
                source_tokens
            ),
        ):

            if (
                _numeric_key(
                    source_tokens[
                        index
                    ][
                        "value"
                    ]
                )
                == total_key
            ):

                position = index
                break

        if position is None:
            return data

        total_positions.append(
            position
        )

        cursor = (
            position
            + 1
        )

    component_tokens_by_period = {}
    off_tokens_by_period = {}

    first_total_position = (
        total_positions[
            0
        ]
    )

    before_first_total = (
        source_tokens[
            :first_total_position
        ]
    )

    if (
        len(
            before_first_total
        )
        < component_count
    ):
        return data

    component_tokens_by_period[
        ordered_periods[
            0
        ]
    ] = (
        before_first_total[
            -component_count:
        ]
    )

    for index in range(
        len(
            ordered_periods
        )
        - 1
    ):

        current_total = (
            total_positions[
                index
            ]
        )

        next_total = (
            total_positions[
                index + 1
            ]
        )

        between = (
            source_tokens[
                current_total + 1:
                next_total
            ]
        )

        required = (
            off_balance_count
            + component_count
        )

        if len(
            between
        ) < required:
            return data

        off_tokens_by_period[
            ordered_periods[
                index
            ]
        ] = (
            between[
                :off_balance_count
            ]
        )

        component_tokens_by_period[
            ordered_periods[
                index + 1
            ]
        ] = (
            between[
                -component_count:
            ]
        )

    after_last_total = (
        source_tokens[
            total_positions[
                -1
            ]
            + 1:
        ]
    )

    if (
        len(
            after_last_total
        )
        >= off_balance_count
    ):

        off_tokens_by_period[
            ordered_periods[
                -1
            ]
        ] = (
            after_last_total[
                :off_balance_count
            ]
        )

    for period in ordered_periods:

        component_tokens = (
            component_tokens_by_period.get(
                period
            )
        )

        if (
            component_tokens
            and len(
                component_tokens
            )
            == component_count
        ):

            for (
                item,
                token,
            ) in zip(
                component_items,
                component_tokens,
            ):

                _set_period_amount_from_source(
                    item=item,
                    period=period,
                    token=token,
                )

        off_tokens = (
            off_tokens_by_period.get(
                period
            )
        )

        if (
            off_tokens
            and len(
                off_tokens
            )
            == off_balance_count
        ):

            for (
                item,
                token,
            ) in zip(
                off_balance_items,
                off_tokens,
            ):

                _set_period_amount_from_source(
                    item=item,
                    period=period,
                    token=token,
                )

    return data


# ==========================================================
# PROFIT & LOSS NORMALIZATION
# ==========================================================


def normalize_profit_and_loss_data(
    data: dict,
):

    mappings = {
        "revenue": {
            "revenue",
            "sales",
            "total revenue",
        },

        "cost_of_sales": {
            "cost of sales",
            "cost of goods sold",
            "cogs",
        },

        "gross_profit": {
            "gross profit",
        },

        "operating_expenses": {
            "operating expenses",
            "operating expense",
        },

        "operating_profit": {
            "operating profit",
        },

        "tax_expense": {
            "tax",
            "tax expense",
            "income tax expense",
        },

        "net_profit": {
            "net profit",
            "net profit for year",
            "profit for the year",
        },

        "interest_earned": {
            "interest earned",
        },

        "other_income": {
            "other income",
        },

        "total_income": {
            "total income",
        },

        "interest_expended": {
            "interest expended",
        },

        "provisions_and_contingencies": {
            "provisions and contingencies",
            "provisions & contingencies",
        },

        "total_expenditure": {
            "total expenditure",
        },

        "net_profit_before_minority_interest": {
            "consolidated net profit before minority interest",
            "net profit before minority interest",
            "net profit for year",
        },

        "minority_interest": {
            "minority interest",
        },

        "share_in_profits_of_associates": {
            "share in profits of associates",
            "share in profit of associates",
        },

        "net_profit_attributable_to_group": {
            "consolidated net profit attributable to the group",
            "net profit attributable to group",
            "net profit attributable to the group",
        },

        "current_profit": {
            "current profit",
        },

        "impact_on_amalgamation": {
            "impact on amalgamation",
            "impact of amalgamation",
        },

        "brought_forward_profit": {
            "brought forward profit",
            "profit brought forward",
        },

        "total_available_for_appropriation": {
            "total available for appropriation",
        },
    }

    for (
        target_field,
        aliases,
    ) in mappings.items():

        copy_line_item_to_field(
            data=data,
            target_field=target_field,
            aliases=aliases,
        )

    return data


# ==========================================================
# CASH FLOW NORMALIZATION
# ==========================================================


def normalize_cash_flow_data(
    data: dict,
):

    mappings = {
        "operating_cash_flow": {
            "net cash flow from operating activities",
            "net cash flows from operating activities",
            "net cash from operating activities",
            "net cash generated from operating activities",
            "net cash generated by operating activities",
            "net cash flow used in from operating activities",
            "cash flow from operating activities",
        },

        "investing_cash_flow": {
            "net cash flow from investing activities",
            "net cash flows from investing activities",
            "net cash used in investing activities",
            "net cash generated from investing activities",
            "cash flow from investing activities",
        },

        "financing_cash_flow": {
            "net cash flow from financing activities",
            "net cash flows from financing activities",
            "net cash generated from financing activities",
            "net cash used in financing activities",
            "cash flow from financing activities",
        },

        "fx_translation_adjustment": {
            "effect of exchange fluctuation on translation reserve",
            "effect of exchange rate changes",
            "effect of exchange rates",
            "foreign exchange adjustment",
            "fx translation adjustment",
            "translation adjustment",
        },

        "net_change_in_cash": {
            "net increase decrease in cash and cash equivalents",
            "net increase in cash and cash equivalents",
            "net decrease in cash and cash equivalents",
            "net change in cash and cash equivalents",
            "net change in cash",
        },

        "opening_cash": {
            "cash and cash equivalents at beginning of year",
            "cash and cash equivalents at beginning of period",
            "cash and cash equivalents as at april 1st schedules 6 and 7",
            "opening cash and cash equivalents",
            "opening cash",
        },

        "closing_cash": {
            "cash and cash equivalents at end of year",
            "cash and cash equivalents at end of period",
            "cash and cash equivalents as at march 31st schedules 6 and 7",
            "closing cash and cash equivalents",
            "closing cash",
        },
    }

    for (
        target_field,
        aliases,
    ) in mappings.items():

        copy_line_item_to_field(
            data=data,
            target_field=target_field,
            aliases=aliases,
        )

    return data


# ==========================================================
# PROMPTS
# ==========================================================


INVOICE_PROMPT = """
Extract this document as an INVOICE or RECEIPT.

Extract every meaningful visible field.

Required dedicated fields include:

- invoice_number
- invoice_date
- due_date
- vendor_name
- customer_name
- currency
- subtotal
- taxable_amount
- tax_amount
- discount
- shipping_handling
- amount_before_rounding
- round_off
- total_amount
- cash_paid
- change

For every visible product/service row preserve meaningful
columns when present:

- description
- item_code / product code
- HSN/SAC
- quantity
- rate_including_tax
- unit_price / rate
- unit / per
- discount_percent
- discount_amount
- final line amount

Do not drop visible discount columns.

LINE DISCOUNT RULES:

If a discount belongs to one individual product row,
populate that row's discount_percent and/or discount_amount.

Example:

Quantity: 6
Rate: 7.44
Discount: 99%
Amount: 0.45

Extract:

quantity = 6
unit_price = 7.44
discount_percent = 99
amount = 0.45

Do NOT calculate the amount yourself.

If a discount is shown as a separate invoice-level
adjustment row, populate top-level discount.

Example:

Item amount 65.90
@DISC 10% -5.59

Then top-level discount = 5.59.

TOTAL RULES:

subtotal:
Use only an explicitly displayed subtotal or clearly
identified subtotal. Do not calculate one.

taxable_amount:
Populate only when an explicit Taxable Amount / Taxable
Value is visible.

amount_before_rounding:
Use for an explicitly displayed payable/intermediate amount
followed by a separate rounding adjustment and final total.

Example:

TOTAL AMT 60.31
ROUNDING ADJ -0.01
RM 60.30

Extract:

amount_before_rounding = 60.31
round_off = -0.01
total_amount = 60.30

round_off:
Preserve positive or negative sign exactly.

cash_paid:
Extract CASH, Cash Paid, Cash Tendered, or equivalent
only when explicitly visible.

change:
Extract visible CHANGE / Change Due.

Do not infer missing values.

Do not compute totals.

Put other useful visible fields that do not have a
dedicated schema field into additional_fields.

Examples include:

- addresses
- GSTIN
- VAT numbers
- phone numbers
- email
- salesperson
- bank information
- reference numbers
- payment terms

INVOICE NUMBER RULE:

Populate invoice_number only when the source clearly supports it
as an invoice number, receipt number, bill number, or transaction
number.

Never use a room number, item code, merchant number, customer
number, phone number, account number, GSTIN, or unrelated
identifier as invoice_number.

If no reliable invoice/receipt number is present, return null.
"""


BALANCE_SHEET_PROMPT = """
Extract this document as a BALANCE SHEET.

Extract:

- company name
- statement title
- statement date
- currency / unit exactly as visible
- every reporting period
- every meaningful visible financial row
- section name for every row when possible
- all comparative-period values

Populate dedicated totals when explicitly visible:

- total_capital_and_liabilities
- total_assets
- total_liabilities
- total_equity

IMPORTANT COMPARATIVE-TABLE ALIGNMENT RULES:

Balance sheets may be flattened by OCR. The source can contain
all row labels first, followed by the numeric values for one
period and then the values for the comparative period.

Do not shift a comparative-period value to the previous or next
row merely because the OCR text is flattened.

Preserve the original row order and map each complete period
block to that same ordered list of row labels.

Rows that appear after the reported Assets Total, such as:

- Contingent liabilities
- Bills for collection
- other memorandum / off-balance-sheet rows

must remain separate visible line items. They are NOT individual
Asset components and must not be used as the value of the next
period's first Asset row.

For example, if the source order is:

ASSETS
Cash
Balances with banks
Investments
Advances
Fixed assets
Other assets
Total
Contingent liabilities
Bills for collection

then EACH reporting period must preserve exactly that same row
order before moving to the next period.

Do not use an off-balance-sheet number as Cash, Investments,
Advances, Fixed assets, Other assets, or another Asset row.

Do not calculate missing totals.

Do not infer a missing value.

Do not change a number to make the statement balance.

Treat bracketed financial values as negative where parentheses
clearly indicate negative values.

A visible dash should normally be null.

Preserve every meaningful row in line_items.

Put other visible non-table fields in additional_fields.
"""


PROFIT_AND_LOSS_PROMPT = """
Extract this document as a PROFIT AND LOSS statement.

Extract:

- company name
- statement title
- statement date
- currency / unit exactly as visible
- all reporting periods
- every meaningful visible income/expense row
- every comparative-period value
- section names where possible

Populate generic fields when explicitly present:

- revenue
- cost_of_sales
- gross_profit
- operating_expenses
- operating_profit
- tax_expense
- net_profit

For banking / financial P&L documents also populate when
explicitly present:

- interest_earned
- other_income
- total_income
- interest_expended
- provisions_and_contingencies
- total_expenditure
- net_profit_before_minority_interest
- minority_interest
- share_in_profits_of_associates
- net_profit_attributable_to_group
- current_profit
- impact_on_amalgamation
- brought_forward_profit
- total_available_for_appropriation

Do not calculate missing values.

Do not create values to make equations balance.

Preserve every meaningful visible row in line_items.

Parentheses should be negative when used as financial
negative notation.

A visible dash should normally be null.
"""


CASH_FLOW_PROMPT = """
Extract this document as a CASH FLOW STATEMENT.

Extract:

- company name
- statement title
- statement date
- currency / unit exactly as visible
- all reporting periods
- all meaningful visible cash-flow rows
- all comparative-period values
- section names where possible

Populate dedicated fields only when explicitly supported:

- operating_cash_flow
- investing_cash_flow
- financing_cash_flow
- fx_translation_adjustment
- net_change_in_cash
- opening_cash
- closing_cash

Use cash_balance_adjustments for explicit cash-balance
adjustments such as:

- cash acquired on amalgamation
- cash acquired through acquisition
- cash acquired through business combination
- another explicit cash adjustment that participates in
  cash movement reconciliation

Do not put ordinary operating/investing/financing rows into
cash_balance_adjustments.

Preserve ALL meaningful rows in line_items.

Do not calculate any missing value.

Do not infer a missing FX adjustment as zero.

Do not infer a missing cash adjustment as zero.

Parentheses indicate negative values where clearly used as
financial negative notation.

A visible dash should normally become null.
"""


# ==========================================================
# GEMINI CALL
# ==========================================================


async def call_gemini_structured(
    document_text: str,
    prompt: str,
    output_schema: type[BaseModel],
):
    """
    Call Gemini with Pydantic structured output.
    """

    if not settings.GEMINI_API_KEY:

        raise ExtractionError(
            "GEMINI_API_KEY is not configured."
        )

    client = genai.Client(
        api_key=(
            settings.GEMINI_API_KEY
        )
    )

    full_prompt = f"""
{prompt}

DOCUMENT TEXT:

{document_text}
"""

    max_attempts = 3

    last_error = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):

        try:

            response = (
                await client.aio.models.generate_content(
                    model=(
                        settings.GEMINI_MODEL
                    ),
                    contents=(
                        full_prompt
                    ),
                    config=(
                        types.GenerateContentConfig(
                            system_instruction=(
                                SYSTEM_PROMPT
                            ),
                            response_mime_type=(
                                "application/json"
                            ),
                            response_schema=(
                                output_schema
                            ),
                            temperature=0,
                        )
                    ),
                )
            )

            parsed = (
                response.parsed
            )

            if parsed is None:

                if not response.text:

                    raise ExtractionError(
                        "Gemini returned an empty "
                        "structured response."
                    )

                parsed = (
                    output_schema
                    .model_validate_json(
                        response.text
                    )
                )

            if isinstance(
                parsed,
                BaseModel,
            ):

                return (
                    parsed.model_dump()
                )

            return (
                output_schema
                .model_validate(
                    parsed
                )
                .model_dump()
            )

        except Exception as error:

            last_error = error

            print(
                f"Gemini extraction attempt "
                f"{attempt}/{max_attempts} failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

            if attempt < max_attempts:

                delay = (
                    2 ** (
                        attempt - 1
                    )
                )

                print(
                    "Retrying Gemini in "
                    f"{delay} second(s)..."
                )

                await asyncio.sleep(
                    delay
                )

    raise ExtractionError(
        "Gemini extraction failed after "
        f"{max_attempts} attempts. "
        "Last error: "
        f"{type(last_error).__name__}"
    )


# ==========================================================
# MAIN EXTRACTION SERVICE
# ==========================================================


async def extract_structured_data(
    document_type: DocumentType,
    document_text: str,
):
    """
    Extract structured information according to the
    user-selected document type.
    """

    if not document_text.strip():

        raise ExtractionError(
            "Document text is empty."
        )

    # ======================================================
    # INVOICE
    # ======================================================

    if (
        document_type
        == DocumentType.INVOICE
    ):

        data = (
            await call_gemini_structured(
                document_text=(
                    document_text
                ),
                prompt=(
                    INVOICE_PROMPT
                ),
                output_schema=(
                    InvoiceExtraction
                ),
            )
        )

        data = (
            normalize_invoice_data(
                data
            )
        )

        return data

    # ======================================================
    # BALANCE SHEET
    # ======================================================

    if (
        document_type
        == DocumentType.BALANCE_SHEET
    ):

        data = (
            await call_gemini_structured(
                document_text=(
                    document_text
                ),
                prompt=(
                    BALANCE_SHEET_PROMPT
                ),
                output_schema=(
                    BalanceSheetExtraction
                ),
            )
        )

        data = (
            normalize_balance_sheet_data(
                data=data,
                document_text=document_text,
            )
        )

        return data

    # ======================================================
    # PROFIT & LOSS
    # ======================================================

    if (
        document_type
        == DocumentType.PROFIT_AND_LOSS
    ):

        data = (
            await call_gemini_structured(
                document_text=(
                    document_text
                ),
                prompt=(
                    PROFIT_AND_LOSS_PROMPT
                ),
                output_schema=(
                    ProfitAndLossExtraction
                ),
            )
        )

        data = (
            normalize_profit_and_loss_data(
                data
            )
        )

        return data

    # ======================================================
    # CASH FLOW
    # ======================================================

    if (
        document_type
        == DocumentType.CASH_FLOW_STATEMENT
    ):

        data = (
            await call_gemini_structured(
                document_text=(
                    document_text
                ),
                prompt=(
                    CASH_FLOW_PROMPT
                ),
                output_schema=(
                    CashFlowExtraction
                ),
            )
        )

        data = (
            normalize_cash_flow_data(
                data
            )
        )

        return data

    raise ExtractionError(
        f"Unsupported document type: "
        f"{document_type}"
    )