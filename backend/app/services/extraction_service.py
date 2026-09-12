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

    # ------------------------------------------------------
    # Receipt-style:
    #
    # TOTAL AMT       60.31
    # ROUNDING ADJ    -0.01
    # final amount    60.30
    #
    # If Gemini placed 60.31 into subtotal, move it to the
    # more accurate amount_before_rounding field when the
    # source relationship itself proves that interpretation.
    # ------------------------------------------------------

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

Do not calculate missing totals.

Do not infer a missing value.

Treat bracketed financial values as negative where
parentheses clearly indicate negative values.

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

                return parsed.model_dump()

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

                delay = 2 ** (
                    attempt - 1
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

        return (
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