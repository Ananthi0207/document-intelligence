from backend.app.services.financial_validation_service import (
    validate_invoice_financials,
)


def field(value):
    return {
        "value": value,
        "evidence": None,
    }


def test_invoice_financial_validation_passes():
    extracted_data = {
        "subtotal": field(100.00),
        "tax_amount": field(10.00),
        "discount": field(None),
        "shipping_handling": field(None),
        "amount_before_rounding": field(None),
        "round_off": field(None),
        "total_amount": field(110.00),
        "cash_paid": field(None),
        "change": field(None),

        "line_items": [
            {
                "description": "Test Product",
                "item_code": None,
                "hsn_sac": None,
                "quantity": 2,
                "rate_including_tax": None,
                "unit_price": 50.00,
                "unit": None,
                "discount_percent": None,
                "discount_amount": None,
                "amount": 100.00,
                "evidence": None,
            }
        ],
    }

    result = validate_invoice_financials(
        extracted_data
    )

    assert result["overall_status"] == "PASS"
    assert result["summary"]["failed"] == 0