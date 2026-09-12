from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}


class DocumentValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_document(filename: str, content: bytes) -> dict:

    # 1. Make sure a filename exists
    if not filename:
        raise DocumentValidationError(
            code="INVALID_FILE_NAME",
            message="File name is missing."
        )

    # 2. Make sure the file isn't empty
    if not content:
        raise DocumentValidationError(
            code="EMPTY_FILE",
            message="Uploaded file is empty."
        )

    # 3. Get the extension
    extension = Path(filename).suffix.lower()

    # 4. Check whether extension is supported
    if extension not in ALLOWED_FILE_TYPES:
        raise DocumentValidationError(
            code="UNSUPPORTED_FILE_TYPE",
            message="Only PDF / JPG / PNG documents are supported."
        )

    # 5. Validate PDF
    if extension == ".pdf":
        page_count = validate_pdf(content)

    # 6. Validate JPG / PNG
    else:
        page_count = validate_image(content)

    # 7. Maximum 3 pages
    if page_count > 3:
        raise DocumentValidationError(
            code="PAGE_LIMIT_EXCEEDED",
            message="Documents must contain no more than 3 pages."
        )

    return {
        "file_type": ALLOWED_FILE_TYPES[extension],
        "is_supported": True,
        "is_readable": True,
        "page_count": page_count,
        "status": "PASS",
    }


def validate_pdf(content: bytes) -> int:
    try:
        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise DocumentValidationError(
                code="UNREADABLE_FILE",
                message="Encrypted PDF files are not supported."
            )

        page_count = len(reader.pages)

        if page_count == 0:
            raise DocumentValidationError(
                code="EMPTY_DOCUMENT",
                message="PDF contains no pages."
            )

        return page_count

    except DocumentValidationError:
        raise

    except Exception:
        raise DocumentValidationError(
            code="CORRUPTED_FILE",
            message="The PDF file is corrupted or unreadable."
        )


def validate_image(content: bytes) -> int:
    try:
        image = Image.open(BytesIO(content))

        # Verify that Pillow can actually decode the image
        image.verify()

        return 1

    except (UnidentifiedImageError, OSError):
        raise DocumentValidationError(
            code="CORRUPTED_FILE",
            message="The image file is corrupted or unreadable."
        )