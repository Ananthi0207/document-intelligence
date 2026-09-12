from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db

import backend.app.api.routes.documents as documents_route


client = TestClient(app)


# ==========================================================
# FAKE DATABASE DEPENDENCY
# ==========================================================


def fake_get_db():
    yield None


# ==========================================================
# API FLOW TEST
# ==========================================================


def test_process_invoice_api_flow(
    monkeypatch,
):

    # ------------------------------------------------------
    # Mock file validation
    # ------------------------------------------------------

    def fake_validate_document(
        filename,
        file_content,
    ):
        return {
            "file_type": "image/jpeg",
            "is_supported": True,
            "is_readable": True,
            "page_count": 1,
            "status": "PASS",
        }

    # ------------------------------------------------------
    # Mock OCR
    # ------------------------------------------------------

    async def fake_extract_document_text(
        filename,
        file_content,
    ):
        return {
            "text": (
                "Invoice INV-001\n"
                "Subtotal: 100\n"
                "Tax: 10\n"
                "Total: 110"
            ),
            "pages": [
                {
                    "page_number": 1,
                    "text": "Fake invoice text",
                    "extraction_method": "ocr",
                    "ocr_provider": "test",
                }
            ],
            "ocr_used": True,
            "ocr_fallback_used": False,
        }

    # ------------------------------------------------------
    # Mock AI structured extraction
    # ------------------------------------------------------

    async def fake_extract_structured_data(
        document_type,
        document_text,
    ):
        return {
            "invoice_number": {
                "value": "INV-001",
                "evidence": None,
            },
            "subtotal": {
                "value": 100.0,
                "evidence": None,
            },
            "tax_amount": {
                "value": 10.0,
                "evidence": None,
            },
            "total_amount": {
                "value": 110.0,
                "evidence": None,
            },
            "line_items": [],
            "additional_fields": [],
        }

    # ------------------------------------------------------
    # Mock financial validation
    # ------------------------------------------------------

    def fake_financial_validation(
        extracted_data,
    ):
        return {
            "overall_status": "PASS",
            "summary": {
                "total_checks": 1,
                "passed": 1,
                "failed": 0,
                "not_applicable": 0,
            },
            "checks": [
                {
                    "check_id": (
                        "total_reconciliation"
                    ),
                    "check_name": (
                        "Invoice total reconciliation"
                    ),
                    "formula": (
                        "subtotal + tax = total"
                    ),
                    "operands": {
                        "subtotal": 100.0,
                        "tax_amount": 10.0,
                    },
                    "calculated_value": 110.0,
                    "reported_value": 110.0,
                    "variance": 0.0,
                    "status": "PASS",
                    "message": (
                        "Financial values reconcile."
                    ),
                }
            ],
        }

    # ------------------------------------------------------
    # Mock database persistence
    # ------------------------------------------------------

    def fake_save_document(**kwargs):
        return None

    # ------------------------------------------------------
    # Apply mocks
    # ------------------------------------------------------

    monkeypatch.setattr(
        documents_route,
        "validate_document",
        fake_validate_document,
    )

    monkeypatch.setattr(
        documents_route,
        "extract_document_text",
        fake_extract_document_text,
    )

    monkeypatch.setattr(
        documents_route,
        "extract_structured_data",
        fake_extract_structured_data,
    )

    monkeypatch.setattr(
        documents_route,
        "validate_invoice_financials",
        fake_financial_validation,
    )

    monkeypatch.setattr(
        documents_route,
        "save_document",
        fake_save_document,
    )

    app.dependency_overrides[
        get_db
    ] = fake_get_db

    try:

        # --------------------------------------------------
        # Call actual FastAPI endpoint
        # --------------------------------------------------

        response = client.post(
            "/api/v1/documents/process",
            files={
                "file": (
                    "sample.jpg",
                    b"fake image bytes",
                    "image/jpeg",
                )
            },
            data={
                "document_type": "invoice",
            },
        )

        # --------------------------------------------------
        # Assertions
        # --------------------------------------------------

        assert response.status_code == 200

        data = response.json()

        assert (
            data["document_name"]
            == "sample.jpg"
        )

        assert (
            data["document_type"]
            == "invoice"
        )

        assert (
            data["processing_status"]
            == "PASS"
        )

        assert (
            data["file_validation"]["status"]
            == "PASS"
        )

        assert (
            data[
                "financial_validation"
            ]["overall_status"]
            == "PASS"
        )

        assert (
            "processing_metadata"
            in data
        )

        assert (
            data[
                "processing_metadata"
            ]["ocr_used"]
            is True
        )

        assert (
            "processing_time_ms"
            in data[
                "processing_metadata"
            ]
        )

    finally:

        app.dependency_overrides.clear()