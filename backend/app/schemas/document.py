from enum import Enum

class DocumentType(str,Enum):
    INVOICE="invoice"
    BALANCE_SHEET="balance_sheet"
    PROFIT_AND_LOSS="profit_and_loss"
    CASH_FLOW_STATEMENT="cash_flow_statement"