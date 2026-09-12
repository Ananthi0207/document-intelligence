from pydantic import BaseModel, Field


# ==========================================================
# COMMON SCHEMAS
# ==========================================================


class Evidence(BaseModel):
    source_text: str | None = None
    page_number: int | None = None


class TextField(BaseModel):
    value: str | None = None
    evidence: Evidence | None = None


class NumericField(BaseModel):
    value: float | None = None
    evidence: Evidence | None = None


class AdditionalField(BaseModel):
    name: str
    value: str | float | int | bool | None = None
    evidence: Evidence | None = None


class PeriodAmount(BaseModel):
    period: str
    value: float | None = None
    evidence: Evidence | None = None


# ==========================================================
# INVOICE
# ==========================================================


class InvoiceLineItem(BaseModel):
    description: str | None = None

    item_code: str | None = None
    hsn_sac: str | None = None

    quantity: float | None = None

    rate_including_tax: float | None = None
    unit_price: float | None = None

    unit: str | None = None

    discount_percent: float | None = None
    discount_amount: float | None = None

    amount: float | None = None

    evidence: Evidence | None = None


class InvoiceExtraction(BaseModel):
    invoice_number: TextField = Field(
        default_factory=TextField
    )

    invoice_date: TextField = Field(
        default_factory=TextField
    )

    due_date: TextField = Field(
        default_factory=TextField
    )

    vendor_name: TextField = Field(
        default_factory=TextField
    )

    customer_name: TextField = Field(
        default_factory=TextField
    )

    currency: TextField = Field(
        default_factory=TextField
    )

    subtotal: NumericField = Field(
        default_factory=NumericField
    )

    taxable_amount: NumericField = Field(
        default_factory=NumericField
    )

    tax_amount: NumericField = Field(
        default_factory=NumericField
    )

    discount: NumericField = Field(
        default_factory=NumericField
    )

    shipping_handling: NumericField = Field(
        default_factory=NumericField
    )

    amount_before_rounding: NumericField = Field(
        default_factory=NumericField
    )

    round_off: NumericField = Field(
        default_factory=NumericField
    )

    total_amount: NumericField = Field(
        default_factory=NumericField
    )

    cash_paid: NumericField = Field(
        default_factory=NumericField
    )

    change: NumericField = Field(
        default_factory=NumericField
    )

    line_items: list[InvoiceLineItem] = Field(
        default_factory=list
    )

    additional_fields: list[AdditionalField] = Field(
        default_factory=list
    )


# ==========================================================
# BALANCE SHEET
# ==========================================================


class BalanceSheetLineItem(BaseModel):
    section: str | None = None
    name: str
    amounts: list[PeriodAmount] = Field(
        default_factory=list
    )


class BalanceSheetExtraction(BaseModel):
    company_name: TextField = Field(
        default_factory=TextField
    )

    statement_title: TextField = Field(
        default_factory=TextField
    )

    statement_date: TextField = Field(
        default_factory=TextField
    )

    currency: TextField = Field(
        default_factory=TextField
    )

    periods: list[str] = Field(
        default_factory=list
    )

    total_capital_and_liabilities: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_assets: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_liabilities: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_equity: list[PeriodAmount] = Field(
        default_factory=list
    )

    line_items: list[BalanceSheetLineItem] = Field(
        default_factory=list
    )

    additional_fields: list[AdditionalField] = Field(
        default_factory=list
    )


# ==========================================================
# PROFIT & LOSS
# ==========================================================


class ProfitAndLossLineItem(BaseModel):
    section: str | None = None
    name: str
    amounts: list[PeriodAmount] = Field(
        default_factory=list
    )


class ProfitAndLossExtraction(BaseModel):
    company_name: TextField = Field(
        default_factory=TextField
    )

    statement_title: TextField = Field(
        default_factory=TextField
    )

    statement_date: TextField = Field(
        default_factory=TextField
    )

    currency: TextField = Field(
        default_factory=TextField
    )

    periods: list[str] = Field(
        default_factory=list
    )

    # Generic P&L fields
    revenue: list[PeriodAmount] = Field(
        default_factory=list
    )

    cost_of_sales: list[PeriodAmount] = Field(
        default_factory=list
    )

    gross_profit: list[PeriodAmount] = Field(
        default_factory=list
    )

    operating_expenses: list[PeriodAmount] = Field(
        default_factory=list
    )

    operating_profit: list[PeriodAmount] = Field(
        default_factory=list
    )

    tax_expense: list[PeriodAmount] = Field(
        default_factory=list
    )

    net_profit: list[PeriodAmount] = Field(
        default_factory=list
    )

    # Banking / financial statement fields
    interest_earned: list[PeriodAmount] = Field(
        default_factory=list
    )

    other_income: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_income: list[PeriodAmount] = Field(
        default_factory=list
    )

    interest_expended: list[PeriodAmount] = Field(
        default_factory=list
    )

    provisions_and_contingencies: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_expenditure: list[PeriodAmount] = Field(
        default_factory=list
    )

    net_profit_before_minority_interest: list[PeriodAmount] = Field(
        default_factory=list
    )

    minority_interest: list[PeriodAmount] = Field(
        default_factory=list
    )

    share_in_profits_of_associates: list[PeriodAmount] = Field(
        default_factory=list
    )

    net_profit_attributable_to_group: list[PeriodAmount] = Field(
        default_factory=list
    )

    current_profit: list[PeriodAmount] = Field(
        default_factory=list
    )

    impact_on_amalgamation: list[PeriodAmount] = Field(
        default_factory=list
    )

    brought_forward_profit: list[PeriodAmount] = Field(
        default_factory=list
    )

    total_available_for_appropriation: list[PeriodAmount] = Field(
        default_factory=list
    )

    line_items: list[ProfitAndLossLineItem] = Field(
        default_factory=list
    )

    additional_fields: list[AdditionalField] = Field(
        default_factory=list
    )


# ==========================================================
# CASH FLOW
# ==========================================================


class CashFlowLineItem(BaseModel):
    section: str | None = None
    name: str
    amounts: list[PeriodAmount] = Field(
        default_factory=list
    )


class CashFlowAdjustment(BaseModel):
    name: str
    amounts: list[PeriodAmount] = Field(
        default_factory=list
    )


class CashFlowExtraction(BaseModel):
    company_name: TextField = Field(
        default_factory=TextField
    )

    statement_title: TextField = Field(
        default_factory=TextField
    )

    statement_date: TextField = Field(
        default_factory=TextField
    )

    currency: TextField = Field(
        default_factory=TextField
    )

    periods: list[str] = Field(
        default_factory=list
    )

    operating_cash_flow: list[PeriodAmount] = Field(
        default_factory=list
    )

    investing_cash_flow: list[PeriodAmount] = Field(
        default_factory=list
    )

    financing_cash_flow: list[PeriodAmount] = Field(
        default_factory=list
    )

    fx_translation_adjustment: list[PeriodAmount] = Field(
        default_factory=list
    )

    net_change_in_cash: list[PeriodAmount] = Field(
        default_factory=list
    )

    opening_cash: list[PeriodAmount] = Field(
        default_factory=list
    )

    closing_cash: list[PeriodAmount] = Field(
        default_factory=list
    )

    cash_balance_adjustments: list[CashFlowAdjustment] = Field(
        default_factory=list
    )

    line_items: list[CashFlowLineItem] = Field(
        default_factory=list
    )

    additional_fields: list[AdditionalField] = Field(
        default_factory=list
    )