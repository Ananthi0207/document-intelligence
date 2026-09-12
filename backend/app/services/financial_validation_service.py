from decimal import (
    Decimal,
    InvalidOperation,
)

from itertools import product


# ==========================================================
# COMMON UTILITIES
# ==========================================================


TOLERANCE = Decimal("0.01")


def to_decimal(value):

    if value is None:
        return None

    try:
        return Decimal(
            str(value)
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        return None


def money_value(value):

    if value is None:
        return None

    return float(
        value.quantize(
            Decimal("0.01")
        )
    )


def get_check_status(
    calculated_value,
    reported_value,
):

    variance = abs(
        calculated_value
        - reported_value
    )

    status = (
        "PASS"
        if variance <= TOLERANCE
        else "FAIL"
    )

    return (
        status,
        variance,
    )


def values_match(
    first,
    second,
):

    if (
        first is None
        or second is None
    ):
        return False

    return (
        abs(
            first
            - second
        )
        <= TOLERANCE
    )


def normalize_text(
    value,
):

    if not value:
        return ""

    normalized = (
        str(value)
        .strip()
        .lower()
        .replace(
            "_",
            " ",
        )
        .replace(
            "&",
            " and ",
        )
    )

    return " ".join(
        normalized.split()
    )


def get_period_value(
    period_amounts,
    period,
):

    for item in period_amounts:

        if (
            str(
                item.get(
                    "period"
                )
            )
            == str(
                period
            )
        ):

            return to_decimal(
                item.get(
                    "value"
                )
            )

    return None


def get_line_item_period_value(
    line_items,
    item_name,
    period,
):

    target = normalize_text(
        item_name
    )

    for item in line_items:

        if (
            normalize_text(
                item.get(
                    "name"
                )
            )
            != target
        ):
            continue

        return get_period_value(
            item.get(
                "amounts",
                [],
            ),
            period,
        )

    return None


def summarize_validations(
    validations,
):

    passed = sum(
        item.get(
            "status"
        )
        == "PASS"
        for item in validations
    )

    failed = sum(
        item.get(
            "status"
        )
        == "FAIL"
        for item in validations
    )

    not_applicable = sum(
        item.get(
            "status"
        )
        == "NOT_APPLICABLE"
        for item in validations
    )

    if failed > 0:

        overall_status = (
            "FAILED"
        )

    elif passed > 0:

        overall_status = (
            "PASS"
        )

    else:

        overall_status = (
            "NOT_APPLICABLE"
        )

    return {
        "overall_status": (
            overall_status
        ),
        "summary": {
            "total_checks": len(
                validations
            ),
            "passed": passed,
            "failed": failed,
            "not_applicable": (
                not_applicable
            ),
        },
        "checks": validations,
    }


# ==========================================================
# ==========================================================
# INVOICE
# ==========================================================
# ==========================================================


def get_invoice_numeric_field(
    extracted_data,
    field_name,
):

    field = extracted_data.get(
        field_name
    )

    if isinstance(
        field,
        dict,
    ):

        return to_decimal(
            field.get(
                "value"
            )
        )

    return to_decimal(
        field
    )


def build_invoice_check(
    check_id,
    check_name,
    formula,
    operands,
    calculated,
    reported,
    missing_message=(
        "One or more required values "
        "are missing."
    ),
):

    if (
        calculated is None
        or reported is None
    ):

        return {
            "check_id": (
                check_id
            ),
            "check_name": (
                check_name
            ),
            "formula": (
                formula
            ),
            "operands": (
                operands
            ),
            "calculated_value": None,
            "reported_value": (
                money_value(
                    reported
                )
            ),
            "variance": None,
            "status": (
                "NOT_APPLICABLE"
            ),
            "message": (
                missing_message
            ),
        }

    status, variance = (
        get_check_status(
            calculated,
            reported,
        )
    )

    return {
        "check_id": check_id,
        "check_name": (
            check_name
        ),
        "formula": formula,
        "operands": operands,
        "calculated_value": (
            money_value(
                calculated
            )
        ),
        "reported_value": (
            money_value(
                reported
            )
        ),
        "variance": (
            money_value(
                variance
            )
        ),
        "status": status,
        "message": (
            "Financial values reconcile."
            if status == "PASS"
            else
            "Financial values do not "
            "reconcile."
        ),
    }


def validate_line_items(
    line_items,
):
    checks = []

    for index, item in enumerate(
        line_items,
        start=1,
    ):
        quantity = to_decimal(
            item.get("quantity")
        )

        unit_price = to_decimal(
            item.get("unit_price")
        )

        amount = to_decimal(
            item.get("amount")
        )

        discount_percent = to_decimal(
            item.get(
                "discount_percent"
            )
        )

        discount_amount = to_decimal(
            item.get(
                "discount_amount"
            )
        )

        description = item.get(
            "description"
        )

        operands = {
            "description": description,
            "quantity": (
                float(quantity)
                if quantity is not None
                else None
            ),
            "unit_price": (
                money_value(
                    unit_price
                )
            ),
            "discount_percent": (
                float(
                    discount_percent
                )
                if discount_percent
                is not None
                else None
            ),
            "discount_amount": (
                money_value(
                    discount_amount
                )
            ),
        }

        if (
            quantity is None
            or unit_price is None
            or amount is None
        ):
            checks.append(
                build_invoice_check(
                    check_id=(
                        f"line_item_{index}_calculation"
                    ),
                    check_name=(
                        f"Line item {index} calculation"
                    ),
                    formula=(
                        "quantity × unit_price = amount"
                    ),
                    operands=operands,
                    calculated=None,
                    reported=amount,
                    missing_message=(
                        "Quantity, unit price, "
                        "or line amount is missing."
                    ),
                )
            )

            continue

        gross_amount = (
            quantity
            * unit_price
        )

        candidates = [
            {
                "formula": (
                    "quantity × unit_price = amount"
                ),
                "calculated": (
                    gross_amount
                ),
            }
        ]

        if discount_amount is not None:
            candidates.append(
                {
                    "formula": (
                        "quantity × unit_price "
                        "- discount_amount = amount"
                    ),
                    "calculated": (
                        gross_amount
                        - discount_amount
                    ),
                }
            )

        if discount_percent is not None:
            candidates.append(
                {
                    "formula": (
                        "quantity × unit_price × "
                        "(1 - discount_percent / 100) "
                        "= amount"
                    ),
                    "calculated": (
                        gross_amount
                        * (
                            Decimal("1")
                            - (
                                discount_percent
                                / Decimal("100")
                            )
                        )
                    ),
                }
            )

        matched = None
        matched_variance = None

        for candidate in candidates:
            status, variance = (
                get_check_status(
                    candidate[
                        "calculated"
                    ],
                    amount,
                )
            )

            if status == "PASS":
                matched = candidate
                matched_variance = variance
                break

        if matched is not None:
            checks.append(
                {
                    "check_id": (
                        f"line_item_{index}_calculation"
                    ),
                    "check_name": (
                        f"Line item {index} calculation"
                    ),
                    "formula": (
                        matched[
                            "formula"
                        ]
                    ),
                    "operands": operands,
                    "calculated_value": (
                        money_value(
                            matched[
                                "calculated"
                            ]
                        )
                    ),
                    "reported_value": (
                        money_value(
                            amount
                        )
                    ),
                    "variance": (
                        money_value(
                            matched_variance
                        )
                    ),
                    "status": "PASS",
                    "message": (
                        "Financial values reconcile."
                    ),
                }
            )

            continue

        best = min(
            candidates,
            key=lambda candidate: abs(
                candidate[
                    "calculated"
                ]
                - amount
            ),
        )

        variance = abs(
            best[
                "calculated"
            ]
            - amount
        )

        checks.append(
            {
                "check_id": (
                    f"line_item_{index}_calculation"
                ),
                "check_name": (
                    f"Line item {index} calculation"
                ),
                "formula": (
                    best[
                        "formula"
                    ]
                ),
                "operands": operands,
                "calculated_value": (
                    money_value(
                        best[
                            "calculated"
                        ]
                    )
                ),
                "reported_value": (
                    money_value(
                        amount
                    )
                ),
                "variance": (
                    money_value(
                        variance
                    )
                ),
                "status": "FAIL",
                "message": (
                    "Financial values do not reconcile."
                ),
            }
        )

    return checks

def validate_invoice_intermediate_total(
    extracted_data,
):

    line_items = extracted_data.get(
        "line_items",
        [],
    )

    subtotal = (
        get_invoice_numeric_field(
            extracted_data,
            "subtotal",
        )
    )

    amount_before_rounding = (
        get_invoice_numeric_field(
            extracted_data,
            "amount_before_rounding",
        )
    )

    discount = (
        get_invoice_numeric_field(
            extracted_data,
            "discount",
        )
    )

    # Prefer an explicit true subtotal.
    # Otherwise use an explicit intermediate total.

    if subtotal is not None:

        reported = subtotal

        target_name = (
            "subtotal"
        )

        check_name = (
            "Line items to subtotal"
        )

    elif (
        amount_before_rounding
        is not None
    ):

        reported = (
            amount_before_rounding
        )

        target_name = (
            "amount_before_rounding"
        )

        check_name = (
            "Line items to "
            "intermediate total"
        )

    else:

        return build_invoice_check(
            check_id=(
                "subtotal_reconciliation"
            ),
            check_name=(
                "Line items reconciliation"
            ),
            formula=None,
            operands={},
            calculated=None,
            reported=None,
            missing_message=(
                "No explicit subtotal or "
                "intermediate total is available."
            ),
        )

    amounts = []

    for item in line_items:

        amount = to_decimal(
            item.get(
                "amount"
            )
        )

        if amount is None:

            return build_invoice_check(
                check_id=(
                    "subtotal_reconciliation"
                ),
                check_name=(
                    check_name
                ),
                formula=None,
                operands={},
                calculated=None,
                reported=(
                    reported
                ),
                missing_message=(
                    "At least one line-item "
                    "amount is missing."
                ),
            )

        amounts.append(
            amount
        )

    if not amounts:

        return build_invoice_check(
            check_id=(
                "subtotal_reconciliation"
            ),
            check_name=(
                check_name
            ),
            formula=None,
            operands={},
            calculated=None,
            reported=(
                reported
            ),
            missing_message=(
                "No line items were extracted."
            ),
        )

    line_sum = sum(
        amounts,
        Decimal("0"),
    )

    candidates = [
        {
            "formula": (
                "sum(line_item.amount) "
                f"= {target_name}"
            ),
            "calculated": (
                line_sum
            ),
        }
    ]

    if discount is not None:

        candidates.append(
            {
                "formula": (
                    "sum(line_item.amount) "
                    "- discount "
                    f"= {target_name}"
                ),
                "calculated": (
                    line_sum
                    - discount
                ),
            }
        )

    for candidate in candidates:

        status, variance = (
            get_check_status(
                candidate[
                    "calculated"
                ],
                reported,
            )
        )

        if status == "PASS":

            return {
                "check_id": (
                    "subtotal_reconciliation"
                ),
                "check_name": (
                    check_name
                ),
                "formula": (
                    candidate[
                        "formula"
                    ]
                ),
                "operands": {
                    "line_item_amounts": [
                        money_value(
                            value
                        )
                        for value
                        in amounts
                    ],
                    "discount": (
                        money_value(
                            discount
                        )
                    ),
                },
                "calculated_value": (
                    money_value(
                        candidate[
                            "calculated"
                        ]
                    )
                ),
                "reported_value": (
                    money_value(
                        reported
                    )
                ),
                "variance": (
                    money_value(
                        variance
                    )
                ),
                "status": "PASS",
                "message": (
                    "Line item amounts "
                    "reconcile."
                ),
            }

    best = min(
        candidates,
        key=lambda candidate: abs(
            candidate[
                "calculated"
            ]
            - reported
        ),
    )

    variance = abs(
        best[
            "calculated"
        ]
        - reported
    )

    return {
        "check_id": (
            "subtotal_reconciliation"
        ),
        "check_name": (
            check_name
        ),
        "formula": (
            best[
                "formula"
            ]
        ),
        "operands": {
            "line_item_amounts": [
                money_value(
                    value
                )
                for value
                in amounts
            ],
            "discount": (
                money_value(
                    discount
                )
            ),
        },
        "calculated_value": (
            money_value(
                best[
                    "calculated"
                ]
            )
        ),
        "reported_value": (
            money_value(
                reported
            )
        ),
        "variance": (
            money_value(
                variance
            )
        ),
        "status": "FAIL",
        "message": (
            "Line item amounts do not "
            "reconcile."
        ),
    }


def validate_taxable_amount(
    extracted_data,
):

    taxable = (
        get_invoice_numeric_field(
            extracted_data,
            "taxable_amount",
        )
    )

    tax = (
        get_invoice_numeric_field(
            extracted_data,
            "tax_amount",
        )
    )

    round_off = (
        get_invoice_numeric_field(
            extracted_data,
            "round_off",
        )
    )

    total = (
        get_invoice_numeric_field(
            extracted_data,
            "total_amount",
        )
    )

    if taxable is None:

        return None

    if (
        tax is None
        or total is None
    ):

        return build_invoice_check(
            check_id=(
                "taxable_amount_reconciliation"
            ),
            check_name=(
                "Taxable amount and tax"
            ),
            formula=(
                "taxable_amount + tax_amount "
                "+ round_off = total"
            ),
            operands={
                "taxable_amount": (
                    money_value(
                        taxable
                    )
                ),
                "tax_amount": (
                    money_value(
                        tax
                    )
                ),
                "round_off": (
                    money_value(
                        round_off
                    )
                ),
            },
            calculated=None,
            reported=(
                total
            ),
            missing_message=(
                "Tax or total is unavailable."
            ),
        )

    rounding = (
        round_off
        if round_off is not None
        else Decimal("0")
    )

    calculated = (
        taxable
        + tax
        + rounding
    )

    return build_invoice_check(
        check_id=(
            "taxable_amount_reconciliation"
        ),
        check_name=(
            "Taxable amount and tax"
        ),
        formula=(
            "taxable_amount + tax_amount "
            "+ round_off = total"
        ),
        operands={
            "taxable_amount": (
                money_value(
                    taxable
                )
            ),
            "tax_amount": (
                money_value(
                    tax
                )
            ),
            "round_off": (
                money_value(
                    round_off
                )
            ),
        },
        calculated=(
            calculated
        ),
        reported=(
            total
        ),
    )


def validate_total(
    extracted_data,
):

    subtotal = (
        get_invoice_numeric_field(
            extracted_data,
            "subtotal",
        )
    )

    tax = (
        get_invoice_numeric_field(
            extracted_data,
            "tax_amount",
        )
    )

    discount = (
        get_invoice_numeric_field(
            extracted_data,
            "discount",
        )
    )

    shipping = (
        get_invoice_numeric_field(
            extracted_data,
            "shipping_handling",
        )
    )

    amount_before_rounding = (
        get_invoice_numeric_field(
            extracted_data,
            "amount_before_rounding",
        )
    )

    round_off = (
        get_invoice_numeric_field(
            extracted_data,
            "round_off",
        )
    )

    total = (
        get_invoice_numeric_field(
            extracted_data,
            "total_amount",
        )
    )

    if total is None:

        return build_invoice_check(
            check_id=(
                "total_reconciliation"
            ),
            check_name=(
                "Invoice total reconciliation"
            ),
            formula=None,
            operands={},
            calculated=None,
            reported=None,
            missing_message=(
                "Reported total is missing."
            ),
        )

    rounding = (
        round_off
        if round_off is not None
        else Decimal("0")
    )

    tax_value = (
        tax
        if tax is not None
        else Decimal("0")
    )

    discount_value = (
        discount
        if discount is not None
        else Decimal("0")
    )

    shipping_value = (
        shipping
        if shipping is not None
        else Decimal("0")
    )

    candidates = []

    # ------------------------------------------------------
    # Explicit amount before rounding
    # ------------------------------------------------------

    if (
        amount_before_rounding
        is not None
    ):

        candidates.append(
            {
                "formula": (
                    "amount_before_rounding "
                    "+ round_off = total"
                ),
                "calculated": (
                    amount_before_rounding
                    + rounding
                ),
            }
        )

    if subtotal is not None:

        # Standard invoice
        candidates.append(
            {
                "formula": (
                    "subtotal + tax_amount + "
                    "shipping_handling - discount "
                    "+ round_off = total"
                ),
                "calculated": (
                    subtotal
                    + tax_value
                    + shipping_value
                    - discount_value
                    + rounding
                ),
            }
        )

        # Discount may already be included in displayed
        # subtotal / intermediate amount.
        if discount is not None:

            candidates.append(
                {
                    "formula": (
                        "subtotal + tax_amount + "
                        "shipping_handling + round_off "
                        "= total "
                        "(discount already reflected)"
                    ),
                    "calculated": (
                        subtotal
                        + tax_value
                        + shipping_value
                        + rounding
                    ),
                }
            )

        # Tax may already be included.
        if tax is not None:

            candidates.append(
                {
                    "formula": (
                        "subtotal + shipping_handling "
                        "- discount + round_off "
                        "= total "
                        "(tax already included)"
                    ),
                    "calculated": (
                        subtotal
                        + shipping_value
                        - discount_value
                        + rounding
                    ),
                }
            )

        # Both tax and discount may already be reflected.
        if (
            tax is not None
            and discount is not None
        ):

            candidates.append(
                {
                    "formula": (
                        "subtotal + shipping_handling "
                        "+ round_off = total "
                        "(tax and discount already reflected)"
                    ),
                    "calculated": (
                        subtotal
                        + shipping_value
                        + rounding
                    ),
                }
            )

    if not candidates:

        return build_invoice_check(
            check_id=(
                "total_reconciliation"
            ),
            check_name=(
                "Invoice total reconciliation"
            ),
            formula=None,
            operands={},
            calculated=None,
            reported=(
                total
            ),
            missing_message=(
                "Insufficient displayed values "
                "for total reconciliation."
            ),
        )

    operands = {
        "subtotal": (
            money_value(
                subtotal
            )
        ),
        "tax_amount": (
            money_value(
                tax
            )
        ),
        "shipping_handling": (
            money_value(
                shipping
            )
        ),
        "discount": (
            money_value(
                discount
            )
        ),
        "amount_before_rounding": (
            money_value(
                amount_before_rounding
            )
        ),
        "round_off": (
            money_value(
                round_off
            )
        ),
    }

    for candidate in candidates:

        status, variance = (
            get_check_status(
                candidate[
                    "calculated"
                ],
                total,
            )
        )

        if status == "PASS":

            return {
                "check_id": (
                    "total_reconciliation"
                ),
                "check_name": (
                    "Invoice total reconciliation"
                ),
                "formula": (
                    candidate[
                        "formula"
                    ]
                ),
                "operands": (
                    operands
                ),
                "calculated_value": (
                    money_value(
                        candidate[
                            "calculated"
                        ]
                    )
                ),
                "reported_value": (
                    money_value(
                        total
                    )
                ),
                "variance": (
                    money_value(
                        variance
                    )
                ),
                "status": "PASS",
                "message": (
                    "Invoice total reconciles."
                ),
            }

    best = min(
        candidates,
        key=lambda candidate: abs(
            candidate[
                "calculated"
            ]
            - total
        ),
    )

    variance = abs(
        best[
            "calculated"
        ]
        - total
    )

    return {
        "check_id": (
            "total_reconciliation"
        ),
        "check_name": (
            "Invoice total reconciliation"
        ),
        "formula": (
            best[
                "formula"
            ]
        ),
        "operands": (
            operands
        ),
        "calculated_value": (
            money_value(
                best[
                    "calculated"
                ]
            )
        ),
        "reported_value": (
            money_value(
                total
            )
        ),
        "variance": (
            money_value(
                variance
            )
        ),
        "status": "FAIL",
        "message": (
            "Invoice total does not reconcile "
            "using supported displayed "
            "relationships."
        ),
    }


def validate_cash_change(
    extracted_data,
):

    cash_paid = (
        get_invoice_numeric_field(
            extracted_data,
            "cash_paid",
        )
    )

    change = (
        get_invoice_numeric_field(
            extracted_data,
            "change",
        )
    )

    total = (
        get_invoice_numeric_field(
            extracted_data,
            "total_amount",
        )
    )

    if (
        cash_paid is None
        and change is None
    ):

        return None

    if (
        cash_paid is None
        or change is None
        or total is None
    ):

        return build_invoice_check(
            check_id=(
                "cash_change_reconciliation"
            ),
            check_name=(
                "Cash paid and change"
            ),
            formula=(
                "cash_paid - total_amount "
                "= change"
            ),
            operands={
                "cash_paid": (
                    money_value(
                        cash_paid
                    )
                ),
                "total_amount": (
                    money_value(
                        total
                    )
                ),
            },
            calculated=None,
            reported=(
                change
            ),
            missing_message=(
                "Cash paid, total, or change "
                "is unavailable."
            ),
        )

    calculated = (
        cash_paid
        - total
    )

    return build_invoice_check(
        check_id=(
            "cash_change_reconciliation"
        ),
        check_name=(
            "Cash paid and change"
        ),
        formula=(
            "cash_paid - total_amount "
            "= change"
        ),
        operands={
            "cash_paid": (
                money_value(
                    cash_paid
                )
            ),
            "total_amount": (
                money_value(
                    total
                )
            ),
        },
        calculated=(
            calculated
        ),
        reported=(
            change
        ),
    )


def validate_invoice_financials(
    extracted_data,
):

    checks = []

    checks.extend(
        validate_line_items(
            extracted_data.get(
                "line_items",
                [],
            )
        )
    )

    checks.append(
        validate_invoice_intermediate_total(
            extracted_data
        )
    )

    taxable_check = (
        validate_taxable_amount(
            extracted_data
        )
    )

    if taxable_check is not None:

        checks.append(
            taxable_check
        )

    checks.append(
        validate_total(
            extracted_data
        )
    )

    cash_check = (
        validate_cash_change(
            extracted_data
        )
    )

    if cash_check is not None:

        checks.append(
            cash_check
        )

    return summarize_validations(
        checks
    )


# ==========================================================
# ==========================================================
# BALANCE SHEET
# ==========================================================
# ==========================================================


def get_section_component_values(
    line_items,
    section_name,
    period,
):

    values = []

    target = normalize_text(
        section_name
    )

    for item in line_items:

        section = normalize_text(
            item.get(
                "section"
            )
        )

        if section != target:
            continue

        name = normalize_text(
            item.get(
                "name"
            )
        )

        if (
            name == "total"
            or name.startswith(
                "total "
            )
        ):
            continue

        value = get_period_value(
            item.get(
                "amounts",
                [],
            ),
            period,
        )

        if value is None:
            return None

        values.append(
            value
        )

    return values or None


def validate_capital_liabilities_to_assets(
    extracted_data,
):

    checks = []

    periods = extracted_data.get(
        "periods",
        [],
    )

    if not periods:

        return [
            {
                "check_id": (
                    "capital_liabilities_vs_assets"
                ),
                "check_name": (
                    "Capital & Liabilities "
                    "to Assets"
                ),
                "formula": None,
                "period": None,
                "operands": {},
                "calculated_value": None,
                "reported_value": None,
                "variance": None,
                "status": (
                    "NOT_APPLICABLE"
                ),
                "message": (
                    "No reporting periods "
                    "were extracted."
                ),
            }
        ]

    for period in periods:

        assets = get_period_value(
            extracted_data.get(
                "total_assets",
                [],
            ),
            period,
        )

        combined = get_period_value(
            extracted_data.get(
                "total_capital_and_liabilities",
                [],
            ),
            period,
        )

        liabilities = get_period_value(
            extracted_data.get(
                "total_liabilities",
                [],
            ),
            period,
        )

        equity = get_period_value(
            extracted_data.get(
                "total_equity",
                [],
            ),
            period,
        )

        if (
            combined is not None
            and assets is not None
        ):

            calculated = combined

            formula = (
                "total_capital_and_liabilities "
                "= total_assets"
            )

            operands = {
                "total_capital_and_liabilities": (
                    money_value(
                        combined
                    )
                )
            }

        elif (
            liabilities is not None
            and equity is not None
            and assets is not None
        ):

            calculated = (
                liabilities
                + equity
            )

            formula = (
                "total_liabilities + "
                "total_equity = total_assets"
            )

            operands = {
                "total_liabilities": (
                    money_value(
                        liabilities
                    )
                ),
                "total_equity": (
                    money_value(
                        equity
                    )
                ),
            }

        else:

            checks.append(
                {
                    "check_id": (
                        "capital_liabilities_vs_assets_"
                        f"{period}"
                    ),
                    "check_name": (
                        "Capital & Liabilities "
                        "to Assets"
                    ),
                    "formula": (
                        "total_capital_and_liabilities "
                        "= total_assets"
                    ),
                    "period": period,
                    "operands": {
                        "total_capital_and_liabilities": (
                            money_value(
                                combined
                            )
                        ),
                        "total_liabilities": (
                            money_value(
                                liabilities
                            )
                        ),
                        "total_equity": (
                            money_value(
                                equity
                            )
                        ),
                    },
                    "calculated_value": None,
                    "reported_value": (
                        money_value(
                            assets
                        )
                    ),
                    "variance": None,
                    "status": (
                        "NOT_APPLICABLE"
                    ),
                    "message": (
                        "Required balance-sheet "
                        "totals are missing."
                    ),
                }
            )

            continue

        status, variance = (
            get_check_status(
                calculated,
                assets,
            )
        )

        checks.append(
            {
                "check_id": (
                    "capital_liabilities_vs_assets_"
                    f"{period}"
                ),
                "check_name": (
                    "Capital & Liabilities "
                    "to Assets"
                ),
                "formula": formula,
                "period": period,
                "operands": operands,
                "calculated_value": (
                    money_value(
                        calculated
                    )
                ),
                "reported_value": (
                    money_value(
                        assets
                    )
                ),
                "variance": (
                    money_value(
                        variance
                    )
                ),
                "status": status,
                "message": (
                    "Balance sheet totals reconcile."
                    if status == "PASS"
                    else
                    "Balance sheet totals do not "
                    "reconcile."
                ),
            }
        )

    return checks


def validate_balance_sheet_section(
    extracted_data,
    section_name,
    reported_field,
    check_prefix,
    check_name,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        components = (
            get_section_component_values(
                line_items=(
                    extracted_data.get(
                        "line_items",
                        [],
                    )
                ),
                section_name=(
                    section_name
                ),
                period=(
                    period
                ),
            )
        )

        reported = get_period_value(
            extracted_data.get(
                reported_field,
                [],
            ),
            period,
        )

        if (
            components is None
            or reported is None
        ):

            checks.append(
                {
                    "check_id": (
                        f"{check_prefix}_{period}"
                    ),
                    "check_name": check_name,
                    "formula": (
                        f"sum({section_name} components) "
                        f"= {reported_field}"
                    ),
                    "period": period,
                    "operands": {},
                    "calculated_value": None,
                    "reported_value": (
                        money_value(
                            reported
                        )
                    ),
                    "variance": None,
                    "status": (
                        "NOT_APPLICABLE"
                    ),
                    "message": (
                        "Insufficient values "
                        "for reconciliation."
                    ),
                }
            )

            continue

        calculated = sum(
            components,
            Decimal("0"),
        )

        status, variance = (
            get_check_status(
                calculated,
                reported,
            )
        )

        checks.append(
            {
                "check_id": (
                    f"{check_prefix}_{period}"
                ),
                "check_name": check_name,
                "formula": (
                    f"sum({section_name} components) "
                    f"= {reported_field}"
                ),
                "period": period,
                "operands": {
                    "component_values": [
                        money_value(
                            value
                        )
                        for value in components
                    ]
                },
                "calculated_value": (
                    money_value(
                        calculated
                    )
                ),
                "reported_value": (
                    money_value(
                        reported
                    )
                ),
                "variance": (
                    money_value(
                        variance
                    )
                ),
                "status": status,
                "message": (
                    "Components reconcile "
                    "to reported total."
                    if status == "PASS"
                    else
                    "Components do not reconcile "
                    "to reported total."
                ),
            }
        )

    return checks


def validate_balance_sheet_financials(
    extracted_data,
):

    checks = []

    checks.extend(
        validate_capital_liabilities_to_assets(
            extracted_data
        )
    )

    checks.extend(
        validate_balance_sheet_section(
            extracted_data=(
                extracted_data
            ),
            section_name=(
                "CAPITAL AND LIABILITIES"
            ),
            reported_field=(
                "total_capital_and_liabilities"
            ),
            check_prefix=(
                "capital_liability_components"
            ),
            check_name=(
                "Capital & Liability components"
            ),
        )
    )

    checks.extend(
        validate_balance_sheet_section(
            extracted_data=(
                extracted_data
            ),
            section_name=(
                "ASSETS"
            ),
            reported_field=(
                "total_assets"
            ),
            check_prefix=(
                "asset_components"
            ),
            check_name=(
                "Asset components"
            ),
        )
    )

    return summarize_validations(
        checks
    )


# ==========================================================
# ==========================================================
# PROFIT & LOSS
# ==========================================================
# ==========================================================


def build_pnl_check(
    check_id,
    check_name,
    formula,
    period,
    operands,
    calculated,
    reported,
):

    if (
        calculated is None
        or reported is None
    ):

        return {
            "check_id": check_id,
            "check_name": check_name,
            "formula": formula,
            "period": period,
            "operands": operands,
            "calculated_value": None,
            "reported_value": (
                money_value(
                    reported
                )
            ),
            "variance": None,
            "status": (
                "NOT_APPLICABLE"
            ),
            "message": (
                "One or more required values "
                "are missing."
            ),
        }

    status, variance = (
        get_check_status(
            calculated,
            reported,
        )
    )

    return {
        "check_id": check_id,
        "check_name": check_name,
        "formula": formula,
        "period": period,
        "operands": operands,
        "calculated_value": (
            money_value(
                calculated
            )
        ),
        "reported_value": (
            money_value(
                reported
            )
        ),
        "variance": (
            money_value(
                variance
            )
        ),
        "status": status,
        "message": (
            "Financial values reconcile."
            if status == "PASS"
            else
            "Financial values do not reconcile."
        ),
    }


def validate_pnl_total_income(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        interest = get_period_value(
            extracted_data.get(
                "interest_earned",
                [],
            ),
            period,
        )

        other = get_period_value(
            extracted_data.get(
                "other_income",
                [],
            ),
            period,
        )

        reported = get_period_value(
            extracted_data.get(
                "total_income",
                [],
            ),
            period,
        )

        calculated = None

        if (
            interest is not None
            and other is not None
        ):

            calculated = (
                interest
                + other
            )

        checks.append(
            build_pnl_check(
                check_id=(
                    f"pnl_total_income_{period}"
                ),
                check_name=(
                    "Total Income"
                ),
                formula=(
                    "interest_earned + other_income "
                    "= total_income"
                ),
                period=period,
                operands={
                    "interest_earned": (
                        money_value(
                            interest
                        )
                    ),
                    "other_income": (
                        money_value(
                            other
                        )
                    ),
                },
                calculated=(
                    calculated
                ),
                reported=(
                    reported
                ),
            )
        )

    return checks


def validate_pnl_total_expenditure(
    extracted_data,
):

    checks = []

    line_items = extracted_data.get(
        "line_items",
        [],
    )

    for period in extracted_data.get(
        "periods",
        [],
    ):

        interest = get_period_value(
            extracted_data.get(
                "interest_expended",
                [],
            ),
            period,
        )

        operating = get_period_value(
            extracted_data.get(
                "operating_expenses",
                [],
            ),
            period,
        )

        if operating is None:

            operating = (
                get_line_item_period_value(
                    line_items,
                    "Operating expenses",
                    period,
                )
            )

        provisions = get_period_value(
            extracted_data.get(
                "provisions_and_contingencies",
                [],
            ),
            period,
        )

        reported = get_period_value(
            extracted_data.get(
                "total_expenditure",
                [],
            ),
            period,
        )

        calculated = None

        if (
            interest is not None
            and operating is not None
            and provisions is not None
        ):

            calculated = (
                interest
                + operating
                + provisions
            )

        checks.append(
            build_pnl_check(
                check_id=(
                    f"pnl_total_expenditure_{period}"
                ),
                check_name=(
                    "Total Expenditure"
                ),
                formula=(
                    "interest_expended + "
                    "operating_expenses + "
                    "provisions_and_contingencies "
                    "= total_expenditure"
                ),
                period=period,
                operands={
                    "interest_expended": (
                        money_value(
                            interest
                        )
                    ),
                    "operating_expenses": (
                        money_value(
                            operating
                        )
                    ),
                    "provisions_and_contingencies": (
                        money_value(
                            provisions
                        )
                    ),
                },
                calculated=(
                    calculated
                ),
                reported=(
                    reported
                ),
            )
        )

    return checks


def validate_pnl_profit_before_minority(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        income = get_period_value(
            extracted_data.get(
                "total_income",
                [],
            ),
            period,
        )

        expenditure = get_period_value(
            extracted_data.get(
                "total_expenditure",
                [],
            ),
            period,
        )

        reported = get_period_value(
            extracted_data.get(
                "net_profit_before_minority_interest",
                [],
            ),
            period,
        )

        calculated = None

        if (
            income is not None
            and expenditure is not None
        ):

            calculated = (
                income
                - expenditure
            )

        checks.append(
            build_pnl_check(
                check_id=(
                    "pnl_profit_before_minority_"
                    f"{period}"
                ),
                check_name=(
                    "Net Profit before "
                    "Minority Interest"
                ),
                formula=(
                    "total_income - "
                    "total_expenditure = "
                    "net_profit_before_minority_interest"
                ),
                period=period,
                operands={
                    "total_income": (
                        money_value(
                            income
                        )
                    ),
                    "total_expenditure": (
                        money_value(
                            expenditure
                        )
                    ),
                },
                calculated=(
                    calculated
                ),
                reported=(
                    reported
                ),
            )
        )

    return checks


def validate_pnl_group_profit(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        before = get_period_value(
            extracted_data.get(
                "net_profit_before_minority_interest",
                [],
            ),
            period,
        )

        minority = get_period_value(
            extracted_data.get(
                "minority_interest",
                [],
            ),
            period,
        )

        associates = get_period_value(
            extracted_data.get(
                "share_in_profits_of_associates",
                [],
            ),
            period,
        )

        reported = get_period_value(
            extracted_data.get(
                "net_profit_attributable_to_group",
                [],
            ),
            period,
        )

        calculated = None

        if (
            before is not None
            and minority is not None
        ):

            calculated = (
                before
                - minority
            )

            if associates is not None:

                calculated += (
                    associates
                )

                formula = (
                    "net_profit_before_minority_interest "
                    "- minority_interest + "
                    "share_in_profits_of_associates "
                    "= net_profit_attributable_to_group"
                )

            else:

                formula = (
                    "net_profit_before_minority_interest "
                    "- minority_interest "
                    "= net_profit_attributable_to_group"
                )

        else:

            formula = (
                "net_profit_before_minority_interest "
                "- minority_interest "
                "= net_profit_attributable_to_group"
            )

        checks.append(
            build_pnl_check(
                check_id=(
                    f"pnl_group_profit_{period}"
                ),
                check_name=(
                    "Net Profit attributable "
                    "to Group"
                ),
                formula=(
                    formula
                ),
                period=(
                    period
                ),
                operands={
                    "net_profit_before_minority_interest": (
                        money_value(
                            before
                        )
                    ),
                    "minority_interest": (
                        money_value(
                            minority
                        )
                    ),
                    "share_in_profits_of_associates": (
                        money_value(
                            associates
                        )
                    ),
                },
                calculated=(
                    calculated
                ),
                reported=(
                    reported
                ),
            )
        )

    return checks


def validate_pnl_appropriation(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        current_profit = (
            get_period_value(
                extracted_data.get(
                    "current_profit",
                    [],
                ),
                period,
            )
        )

        group_profit = (
            get_period_value(
                extracted_data.get(
                    "net_profit_attributable_to_group",
                    [],
                ),
                period,
            )
        )

        impact = (
            get_period_value(
                extracted_data.get(
                    "impact_on_amalgamation",
                    [],
                ),
                period,
            )
        )

        brought_forward = (
            get_period_value(
                extracted_data.get(
                    "brought_forward_profit",
                    [],
                ),
                period,
            )
        )

        reported = (
            get_period_value(
                extracted_data.get(
                    "total_available_for_appropriation",
                    [],
                ),
                period,
            )
        )

        if (
            current_profit is None
            and group_profit is None
            and brought_forward is None
            and reported is None
        ):

            continue

        calculated = None
        operands = {}

        if (
            current_profit is not None
            and brought_forward is not None
        ):

            calculated = (
                current_profit
                + brought_forward
            )

            formula = (
                "current_profit + "
                "brought_forward_profit = "
                "total_available_for_appropriation"
            )

            operands = {
                "current_profit": (
                    money_value(
                        current_profit
                    )
                ),
                "brought_forward_profit": (
                    money_value(
                        brought_forward
                    )
                ),
            }

        elif (
            group_profit is not None
            and brought_forward is not None
        ):

            calculated = (
                group_profit
                + brought_forward
            )

            if impact is not None:

                calculated += (
                    impact
                )

                formula = (
                    "net_profit_attributable_to_group "
                    "+ impact_on_amalgamation + "
                    "brought_forward_profit = "
                    "total_available_for_appropriation"
                )

            else:

                formula = (
                    "net_profit_attributable_to_group "
                    "+ brought_forward_profit = "
                    "total_available_for_appropriation"
                )

            operands = {
                "net_profit_attributable_to_group": (
                    money_value(
                        group_profit
                    )
                ),
                "impact_on_amalgamation": (
                    money_value(
                        impact
                    )
                ),
                "brought_forward_profit": (
                    money_value(
                        brought_forward
                    )
                ),
            }

        else:

            formula = (
                "current_profit + "
                "brought_forward_profit = "
                "total_available_for_appropriation"
            )

            operands = {
                "current_profit": (
                    money_value(
                        current_profit
                    )
                ),
                "net_profit_attributable_to_group": (
                    money_value(
                        group_profit
                    )
                ),
                "impact_on_amalgamation": (
                    money_value(
                        impact
                    )
                ),
                "brought_forward_profit": (
                    money_value(
                        brought_forward
                    )
                ),
            }

        checks.append(
            build_pnl_check(
                check_id=(
                    f"pnl_appropriation_{period}"
                ),
                check_name=(
                    "Profit available "
                    "for appropriation"
                ),
                formula=(
                    formula
                ),
                period=(
                    period
                ),
                operands=(
                    operands
                ),
                calculated=(
                    calculated
                ),
                reported=(
                    reported
                ),
            )
        )

    return checks


def validate_profit_and_loss_financials(
    extracted_data,
):

    checks = []

    checks.extend(
        validate_pnl_total_income(
            extracted_data
        )
    )

    checks.extend(
        validate_pnl_total_expenditure(
            extracted_data
        )
    )

    checks.extend(
        validate_pnl_profit_before_minority(
            extracted_data
        )
    )

    checks.extend(
        validate_pnl_group_profit(
            extracted_data
        )
    )

    checks.extend(
        validate_pnl_appropriation(
            extracted_data
        )
    )

    return summarize_validations(
        checks
    )


# ==========================================================
# ==========================================================
# CASH FLOW
# ==========================================================
# ==========================================================


def build_cash_flow_check(
    check_id,
    check_name,
    formula,
    period,
    operands,
    calculated,
    reported,
    unresolved=False,
):

    if (
        calculated is None
        or reported is None
        or unresolved
    ):

        return {
            "check_id": check_id,
            "check_name": check_name,
            "formula": formula,
            "period": period,
            "operands": operands,
            "calculated_value": None,
            "reported_value": (
                money_value(
                    reported
                )
            ),
            "variance": None,
            "status": (
                "NOT_APPLICABLE"
            ),
            "message": (
                "Required values are missing, "
                "unreadable, or adjustment "
                "placement could not be "
                "determined reliably."
            ),
        }

    status, variance = (
        get_check_status(
            calculated,
            reported,
        )
    )

    return {
        "check_id": check_id,
        "check_name": check_name,
        "formula": formula,
        "period": period,
        "operands": operands,
        "calculated_value": (
            money_value(
                calculated
            )
        ),
        "reported_value": (
            money_value(
                reported
            )
        ),
        "variance": (
            money_value(
                variance
            )
        ),
        "status": status,
        "message": (
            "Financial values reconcile."
            if status == "PASS"
            else
            "Financial values do not reconcile."
        ),
    }


def get_period_amount_item(
    period_amounts,
    period,
):

    for item in period_amounts:

        if (
            str(
                item.get(
                    "period"
                )
            )
            == str(
                period
            )
        ):

            return item

    return None


def is_explicit_dash(
    period_item,
):

    if not period_item:
        return False

    if (
        period_item.get(
            "value"
        )
        is not None
    ):

        return False

    evidence = (
        period_item.get(
            "evidence"
        )
        or {}
    )

    source_text = str(
        evidence.get(
            "source_text",
            "",
        )
    ).strip()

    if not source_text:
        return False

    return (
        source_text.endswith("-")
        or source_text.endswith("—")
        or source_text.endswith("–")
    )


def get_cash_flow_line_index(
    line_items,
    item_name,
):

    target = normalize_text(
        item_name
    )

    for (
        index,
        item,
    ) in enumerate(
        line_items
    ):

        if (
            normalize_text(
                item.get(
                    "name"
                )
            )
            == target
        ):

            return index

    return None


def get_net_change_line_index(
    line_items,
):

    aliases = {
        normalize_text(
            "Net increase / (decrease) "
            "in cash and cash equivalents"
        ),
        normalize_text(
            "Net increase/(decrease) "
            "in cash and cash equivalents"
        ),
        normalize_text(
            "Net increase / decrease "
            "in cash and cash equivalents"
        ),
        normalize_text(
            "Net increase in cash "
            "and cash equivalents"
        ),
        normalize_text(
            "Net decrease in cash "
            "and cash equivalents"
        ),
        normalize_text(
            "Net change in cash "
            "and cash equivalents"
        ),
        normalize_text(
            "Net change in cash"
        ),
    }

    for (
        index,
        item,
    ) in enumerate(
        line_items
    ):

        if (
            normalize_text(
                item.get(
                    "name"
                )
            )
            in aliases
        ):

            return index

    return None


def classify_adjustments_by_source_order(
    extracted_data,
):

    line_items = extracted_data.get(
        "line_items",
        [],
    )

    adjustments = extracted_data.get(
        "cash_balance_adjustments",
        [],
    )

    net_index = (
        get_net_change_line_index(
            line_items
        )
    )

    before = []
    after = []
    unknown = []

    for adjustment in adjustments:

        adjustment_index = (
            get_cash_flow_line_index(
                line_items,
                adjustment.get(
                    "name"
                ),
            )
        )

        if (
            adjustment_index is None
            or net_index is None
        ):

            unknown.append(
                adjustment
            )

        elif (
            adjustment_index
            < net_index
        ):

            before.append(
                adjustment
            )

        else:

            after.append(
                adjustment
            )

    return (
        before,
        after,
        unknown,
    )


def read_adjustments_for_period(
    adjustments,
    period,
):

    entries = []
    operands = []

    missing = False

    for adjustment in adjustments:

        period_item = (
            get_period_amount_item(
                adjustment.get(
                    "amounts",
                    [],
                ),
                period,
            )
        )

        value = None

        if period_item is not None:

            value = to_decimal(
                period_item.get(
                    "value"
                )
            )

        if value is not None:

            entries.append(
                {
                    "name": (
                        adjustment.get(
                            "name"
                        )
                    ),
                    "value": value,
                }
            )

            operands.append(
                {
                    "name": (
                        adjustment.get(
                            "name"
                        )
                    ),
                    "value": (
                        money_value(
                            value
                        )
                    ),
                    "status": (
                        "PRESENT"
                    ),
                }
            )

        elif is_explicit_dash(
            period_item
        ):

            operands.append(
                {
                    "name": (
                        adjustment.get(
                            "name"
                        )
                    ),
                    "value": None,
                    "status": (
                        "NOT_APPLICABLE"
                    ),
                }
            )

        else:

            missing = True

            operands.append(
                {
                    "name": (
                        adjustment.get(
                            "name"
                        )
                    ),
                    "value": None,
                    "status": (
                        "MISSING"
                    ),
                }
            )

    return (
        entries,
        operands,
        missing,
    )


def adjustment_entries_sum(
    entries,
):

    return sum(
        (
            item[
                "value"
            ]
            for item in entries
        ),
        Decimal("0"),
    )


def resolve_unknown_adjustment_placement(
    unknown_entries,
    base_net_calculation,
    reported_net_change,
    base_closing_calculation,
    reported_closing_cash,
):

    if not unknown_entries:

        return (
            [],
            [],
            True,
        )

    if (
        base_net_calculation is None
        or reported_net_change is None
        or base_closing_calculation is None
        or reported_closing_cash is None
    ):

        return (
            [],
            [],
            False,
        )

    non_zero = [
        entry
        for entry in unknown_entries
        if entry[
            "value"
        ] != 0
    ]

    zero_entries = [
        entry
        for entry in unknown_entries
        if entry[
            "value"
        ] == 0
    ]

    if not non_zero:

        return (
            zero_entries,
            [],
            True,
        )

    if len(
        non_zero
    ) > 12:

        return (
            [],
            [],
            False,
        )

    valid_solutions = []

    for placement in product(
        [0, 1],
        repeat=len(
            non_zero
        ),
    ):

        pre = []
        post = []

        for (
            index,
            flag,
        ) in enumerate(
            placement
        ):

            entry = (
                non_zero[
                    index
                ]
            )

            if flag == 1:

                pre.append(
                    entry
                )

            else:

                post.append(
                    entry
                )

        pre = (
            zero_entries
            + pre
        )

        candidate_net = (
            base_net_calculation
            + adjustment_entries_sum(
                pre
            )
        )

        candidate_closing = (
            base_closing_calculation
            + adjustment_entries_sum(
                post
            )
        )

        if (
            values_match(
                candidate_net,
                reported_net_change,
            )
            and values_match(
                candidate_closing,
                reported_closing_cash,
            )
        ):

            valid_solutions.append(
                (
                    pre,
                    post,
                )
            )

    if len(
        valid_solutions
    ) == 1:

        return (
            valid_solutions[0][0],
            valid_solutions[0][1],
            True,
        )

    return (
        [],
        [],
        False,
    )


def format_adjustment_operands(
    entries,
    placement,
):

    return [
        {
            "name": item[
                "name"
            ],
            "value": (
                money_value(
                    item[
                        "value"
                    ]
                )
            ),
            "status": (
                "PRESENT"
            ),
            "placement": (
                placement
            ),
        }
        for item in entries
    ]


def build_cash_flow_period_context(
    extracted_data,
    period,
):

    operating = get_period_value(
        extracted_data.get(
            "operating_cash_flow",
            [],
        ),
        period,
    )

    investing = get_period_value(
        extracted_data.get(
            "investing_cash_flow",
            [],
        ),
        period,
    )

    financing = get_period_value(
        extracted_data.get(
            "financing_cash_flow",
            [],
        ),
        period,
    )

    reported_net = get_period_value(
        extracted_data.get(
            "net_change_in_cash",
            [],
        ),
        period,
    )

    opening = get_period_value(
        extracted_data.get(
            "opening_cash",
            [],
        ),
        period,
    )

    closing = get_period_value(
        extracted_data.get(
            "closing_cash",
            [],
        ),
        period,
    )

    fx_field = extracted_data.get(
        "fx_translation_adjustment",
        [],
    )

    fx_present = bool(
        fx_field
    )

    fx_value = None
    fx_missing = False

    if fx_present:

        fx_item = (
            get_period_amount_item(
                fx_field,
                period,
            )
        )

        if fx_item is None:

            fx_missing = True

        else:

            fx_value = to_decimal(
                fx_item.get(
                    "value"
                )
            )

            if (
                fx_value is None
                and not is_explicit_dash(
                    fx_item
                )
            ):

                fx_missing = True

    (
        known_pre,
        known_post,
        unknown,
    ) = (
        classify_adjustments_by_source_order(
            extracted_data
        )
    )

    (
        known_pre_entries,
        known_pre_operands,
        known_pre_missing,
    ) = (
        read_adjustments_for_period(
            known_pre,
            period,
        )
    )

    (
        known_post_entries,
        known_post_operands,
        known_post_missing,
    ) = (
        read_adjustments_for_period(
            known_post,
            period,
        )
    )

    (
        unknown_entries,
        unknown_operands,
        unknown_missing,
    ) = (
        read_adjustments_for_period(
            unknown,
            period,
        )
    )

    base_net = None

    if (
        operating is not None
        and investing is not None
        and financing is not None
        and not fx_missing
        and not known_pre_missing
    ):

        base_net = (
            operating
            + investing
            + financing
        )

        if fx_value is not None:

            base_net += (
                fx_value
            )

        base_net += (
            adjustment_entries_sum(
                known_pre_entries
            )
        )

    base_closing = None

    if (
        opening is not None
        and reported_net is not None
        and not known_post_missing
    ):

        base_closing = (
            opening
            + reported_net
            + adjustment_entries_sum(
                known_post_entries
            )
        )

    resolved_pre = []
    resolved_post = []

    resolved = True

    if unknown_missing:

        resolved = False

    elif unknown_entries:

        (
            resolved_pre,
            resolved_post,
            resolved,
        ) = (
            resolve_unknown_adjustment_placement(
                unknown_entries=(
                    unknown_entries
                ),
                base_net_calculation=(
                    base_net
                ),
                reported_net_change=(
                    reported_net
                ),
                base_closing_calculation=(
                    base_closing
                ),
                reported_closing_cash=(
                    closing
                ),
            )
        )

    calculated_net = None

    calculated_closing = None

    if (
        base_net is not None
        and resolved
    ):

        calculated_net = (
            base_net
            + adjustment_entries_sum(
                resolved_pre
            )
        )

    if (
        base_closing is not None
        and resolved
    ):

        calculated_closing = (
            base_closing
            + adjustment_entries_sum(
                resolved_post
            )
        )

    pre_operands = (
        list(
            known_pre_operands
        )
    )

    pre_operands.extend(
        format_adjustment_operands(
            resolved_pre,
            "BEFORE_NET_CHANGE",
        )
    )

    post_operands = (
        list(
            known_post_operands
        )
    )

    post_operands.extend(
        format_adjustment_operands(
            resolved_post,
            "AFTER_NET_CHANGE",
        )
    )

    if (
        unknown_entries
        and not resolved
    ):

        for operand in unknown_operands:

            unresolved_operand = (
                dict(
                    operand
                )
            )

            unresolved_operand[
                "placement"
            ] = "UNRESOLVED"

            pre_operands.append(
                unresolved_operand
            )

    net_parts = [
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
    ]

    if fx_present:

        net_parts.append(
            "fx_translation_adjustment"
        )

    if (
        known_pre_entries
        or resolved_pre
    ):

        net_parts.append(
            "pre_net_change_adjustments"
        )

    net_formula = (
        " + ".join(
            net_parts
        )
        + " = net_change_in_cash"
    )

    if (
        known_post_entries
        or resolved_post
    ):

        closing_formula = (
            "opening_cash + "
            "net_change_in_cash + "
            "post_net_change_adjustments "
            "= closing_cash"
        )

    else:

        closing_formula = (
            "opening_cash + "
            "net_change_in_cash "
            "= closing_cash"
        )

    return {
        "operating": operating,
        "investing": investing,
        "financing": financing,
        "fx_value": fx_value,
        "reported_net_change": (
            reported_net
        ),
        "opening_cash": opening,
        "closing_cash": closing,
        "calculated_net": (
            calculated_net
        ),
        "calculated_closing": (
            calculated_closing
        ),
        "pre_operands": (
            pre_operands
        ),
        "post_operands": (
            post_operands
        ),
        "placement_resolved": (
            resolved
        ),
        "net_formula": (
            net_formula
        ),
        "closing_formula": (
            closing_formula
        ),
    }


def validate_cash_flow_net_change(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        context = (
            build_cash_flow_period_context(
                extracted_data,
                period,
            )
        )

        checks.append(
            build_cash_flow_check(
                check_id=(
                    f"cash_flow_net_change_"
                    f"{period}"
                ),
                check_name=(
                    "Net Change in Cash"
                ),
                formula=(
                    context[
                        "net_formula"
                    ]
                ),
                period=(
                    period
                ),
                operands={
                    "operating_cash_flow": (
                        money_value(
                            context[
                                "operating"
                            ]
                        )
                    ),
                    "investing_cash_flow": (
                        money_value(
                            context[
                                "investing"
                            ]
                        )
                    ),
                    "financing_cash_flow": (
                        money_value(
                            context[
                                "financing"
                            ]
                        )
                    ),
                    "fx_translation_adjustment": (
                        money_value(
                            context[
                                "fx_value"
                            ]
                        )
                    ),
                    "pre_net_change_adjustments": (
                        context[
                            "pre_operands"
                        ]
                    ),
                },
                calculated=(
                    context[
                        "calculated_net"
                    ]
                ),
                reported=(
                    context[
                        "reported_net_change"
                    ]
                ),
                unresolved=(
                    not context[
                        "placement_resolved"
                    ]
                ),
            )
        )

    return checks


def validate_cash_flow_closing_cash(
    extracted_data,
):

    checks = []

    for period in extracted_data.get(
        "periods",
        [],
    ):

        context = (
            build_cash_flow_period_context(
                extracted_data,
                period,
            )
        )

        checks.append(
            build_cash_flow_check(
                check_id=(
                    f"cash_flow_closing_cash_"
                    f"{period}"
                ),
                check_name=(
                    "Closing Cash Reconciliation"
                ),
                formula=(
                    context[
                        "closing_formula"
                    ]
                ),
                period=(
                    period
                ),
                operands={
                    "opening_cash": (
                        money_value(
                            context[
                                "opening_cash"
                            ]
                        )
                    ),
                    "net_change_in_cash": (
                        money_value(
                            context[
                                "reported_net_change"
                            ]
                        )
                    ),
                    "post_net_change_adjustments": (
                        context[
                            "post_operands"
                        ]
                    ),
                },
                calculated=(
                    context[
                        "calculated_closing"
                    ]
                ),
                reported=(
                    context[
                        "closing_cash"
                    ]
                ),
                unresolved=(
                    not context[
                        "placement_resolved"
                    ]
                ),
            )
        )

    return checks


def validate_cash_flow_financials(
    extracted_data,
):

    checks = []

    checks.extend(
        validate_cash_flow_net_change(
            extracted_data
        )
    )

    checks.extend(
        validate_cash_flow_closing_cash(
            extracted_data
        )
    )

    return summarize_validations(
        checks
    )