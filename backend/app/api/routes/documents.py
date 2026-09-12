import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)

from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session


from backend.app.core.database import (
    get_db,
)

from backend.app.schemas.document import (
    DocumentType,
)

from backend.app.services.document_validation_service import (
    DocumentValidationError,
    validate_document,
)

from backend.app.services.ocr_service import (
    TextExtractionError,
    extract_document_text,
)

from backend.app.services.extraction_service import (
    ExtractionError,
    extract_structured_data,
)

from backend.app.services.financial_validation_service import (
    validate_invoice_financials,
    validate_balance_sheet_financials,
    validate_profit_and_loss_financials,
    validate_cash_flow_financials,
)

from backend.app.repositories.document_repository import (
    save_document,
    get_all_documents,
    get_latest_document_by_name,
)


# ==========================================================
# ROUTER
# ==========================================================


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


# ==========================================================
# POST
# PROCESS DOCUMENT
# ==========================================================


@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    db: Session = Depends(get_db),
):

    try:

        # ==================================================
        # 1. READ UPLOADED FILE
        # ==================================================

        file_content = await file.read()

        # ==================================================
        # 2. FILE VALIDATION
        #
        # IMPORTANT:
        # Positional arguments are used intentionally.
        # ==================================================

        file_validation = validate_document(
            file.filename,
            file_content,
        )

        # ==================================================
        # 3. TEXT EXTRACTION / OCR
        #
        # IMPORTANT:
        # Positional arguments are used intentionally.
        # ==================================================

        text_extraction = (
            await extract_document_text(
                file.filename,
                file_content,
            )
        )

        document_text = (
            text_extraction.get(
                "text",
                "",
            )
        )

        # ==================================================
        # 4. AI STRUCTURED EXTRACTION
        # ==================================================

        extracted_data = (
            await extract_structured_data(
                document_type=document_type,
                document_text=document_text,
            )
        )

        # ==================================================
        # 5. FINANCIAL VALIDATION
        # ==================================================

        # --------------------------------------------------
        # INVOICE
        # --------------------------------------------------

        if (
            document_type
            == DocumentType.INVOICE
        ):

            financial_validation = (
                validate_invoice_financials(
                    extracted_data
                )
            )

        # --------------------------------------------------
        # BALANCE SHEET
        # --------------------------------------------------

        elif (
            document_type
            == DocumentType.BALANCE_SHEET
        ):

            financial_validation = (
                validate_balance_sheet_financials(
                    extracted_data
                )
            )

        # --------------------------------------------------
        # PROFIT & LOSS
        # --------------------------------------------------

        elif (
            document_type
            == DocumentType.PROFIT_AND_LOSS
        ):

            financial_validation = (
                validate_profit_and_loss_financials(
                    extracted_data
                )
            )

        # --------------------------------------------------
        # CASH FLOW STATEMENT
        # --------------------------------------------------

        elif (
            document_type
            == DocumentType.CASH_FLOW_STATEMENT
        ):

            financial_validation = (
                validate_cash_flow_financials(
                    extracted_data
                )
            )

        # --------------------------------------------------
        # UNKNOWN TYPE
        # --------------------------------------------------

        else:

            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": (
                            "DOCUMENT_TYPE_NOT_IMPLEMENTED"
                        ),
                        "message": (
                            "Financial validation for "
                            f"'{document_type.value}' "
                            "is not implemented yet."
                        ),
                    }
                },
            )

        # ==================================================
        # 6. BUILD FINAL RESPONSE
        # ==================================================

        result = {
            "message": (
                "Document processed successfully"
            ),
            "document_name": (
                file.filename
            ),
            "document_type": (
                document_type.value
            ),
            "file_validation": (
                file_validation
            ),
            "text_extraction": (
                text_extraction
            ),
            "extracted_data": (
                extracted_data
            ),
            "financial_validation": (
                financial_validation
            ),
        }

        # ==================================================
        # 7. SAVE RESULT TO DATABASE
        # ==================================================

        save_document(
            db=db,
            document_name=file.filename,
            document_type=(
                document_type.value
            ),
            status=(
                financial_validation.get(
                    "overall_status",
                    "NOT_APPLICABLE",
                )
            ),
            result=result,
        )

        # ==================================================
        # 8. RETURN FINAL RESPONSE
        # ==================================================

        return result

    # ======================================================
    # FILE VALIDATION ERROR
    # ======================================================

    except DocumentValidationError as error:

        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": (
                        error.code
                    ),
                    "message": (
                        error.message
                    ),
                }
            },
        )

    # ======================================================
    # OCR / TEXT EXTRACTION ERROR
    # ======================================================

    except TextExtractionError as error:

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": (
                        "TEXT_EXTRACTION_FAILED"
                    ),
                    "message": (
                        str(error)
                    ),
                }
            },
        )

    # ======================================================
    # GEMINI / STRUCTURED EXTRACTION ERROR
    # ======================================================

    except ExtractionError as error:

        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": (
                        "STRUCTURED_EXTRACTION_FAILED"
                    ),
                    "message": (
                        str(error)
                    ),
                }
            },
        )

    # ======================================================
    # UNEXPECTED ERROR
    # ======================================================

    except Exception as error:

        print(
            "Unexpected document processing error:",
            type(error).__name__,
            str(error),
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": (
                        "DOCUMENT_PROCESSING_FAILED"
                    ),
                    "message": (
                        "An unexpected error occurred "
                        "while processing the document."
                    ),
                }
            },
        )


# ==========================================================
# GET
# LIST ALL PROCESSED DOCUMENTS
# ==========================================================


@router.get("")
def list_documents(
    db: Session = Depends(get_db),
):

    documents = (
        get_all_documents(
            db
        )
    )

    return [
        {
            "id": (
                document.id
            ),
            "document_name": (
                document.document_name
            ),
            "document_type": (
                document.document_type
            ),
            "status": (
                document.status
            ),
            "created_at": (
                document.created_at
            ),
        }
        for document in documents
    ]


# ==========================================================
# GET
# LATEST DOCUMENT BY FILE NAME
# ==========================================================


@router.get("/{document_name}")
def get_document(
    document_name: str,
    db: Session = Depends(get_db),
):

    document = (
        get_latest_document_by_name(
            db,
            document_name,
        )
    )

    if document is None:

        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": (
                        "DOCUMENT_NOT_FOUND"
                    ),
                    "message": (
                        "No processed document "
                        "was found with this name."
                    ),
                }
            },
        )

    return json.loads(
        document.result_json
    )