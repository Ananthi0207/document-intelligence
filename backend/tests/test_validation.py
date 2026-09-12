import pytest

from backend.app.services.document_validation_service import (
    DocumentValidationError,
    validate_document,
)


def test_rejects_unsupported_file_type():
    with pytest.raises(DocumentValidationError):
        validate_document(
            "sample.txt",
            b"This is not a supported document.",
        )