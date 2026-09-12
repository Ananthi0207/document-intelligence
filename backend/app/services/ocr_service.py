from io import BytesIO
from pathlib import Path

import httpx
import pymupdf

from google import genai
from google.genai import types
from pypdf import PdfReader

from backend.app.core.config import (
    OCR_SPACE_API_KEY,
    OCR_SPACE_API_URL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)


class TextExtractionError(Exception):
    pass


# ==========================================================
# MAIN DOCUMENT TEXT EXTRACTION ENTRY POINT
# ==========================================================

async def extract_document_text(
    filename: str,
    content: bytes,
) -> dict:
    """
    Extract text from PDF, JPG or PNG documents.

    PDF:
        - use native embedded text when available
        - OCR image-only/scanned pages

    JPG/PNG:
        - OCR directly

    OCR strategy:
        1. Try OCR.Space
        2. If OCR.Space fails, fall back to Gemini Vision
    """

    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return await extract_pdf_text(content)

    if extension in {".jpg", ".jpeg", ".png"}:
        return await extract_image_text(
            filename=filename,
            content=content,
        )

    raise TextExtractionError(
        f"Text extraction is not supported for {extension}"
    )


# ==========================================================
# PDF EXTRACTION
# ==========================================================

async def extract_pdf_text(
    content: bytes,
) -> dict:

    try:
        reader = PdfReader(BytesIO(content))

        pages = []

        for page_index, page in enumerate(reader.pages):

            page_number = page_index + 1

            # ------------------------------------------------
            # First try native PDF text extraction
            # ------------------------------------------------

            native_text = page.extract_text() or ""
            native_text = native_text.strip()

            if native_text:

                pages.append(
                    {
                        "page_number": page_number,
                        "text": native_text,
                        "extraction_method": "native",
                        "ocr_provider": None,
                    }
                )

            else:

                # --------------------------------------------
                # Scanned/image-only PDF page
                #
                # Convert PDF page -> PNG -> OCR
                # --------------------------------------------

                image_bytes = render_pdf_page(
                    content=content,
                    page_index=page_index,
                )

                ocr_result = await perform_ocr(
                    image_bytes=image_bytes,
                    filename=f"page_{page_number}.png",
                )

                pages.append(
                    {
                        "page_number": page_number,
                        "text": ocr_result["text"],
                        "extraction_method": "ocr",
                        "ocr_provider": ocr_result["provider"],
                    }
                )

        return build_text_result(pages)

    except TextExtractionError:
        raise

    except Exception as error:
        raise TextExtractionError(
            "Failed to extract text from PDF."
        ) from error


# ==========================================================
# IMAGE EXTRACTION
# ==========================================================

async def extract_image_text(
    filename: str,
    content: bytes,
) -> dict:

    ocr_result = await perform_ocr(
        image_bytes=content,
        filename=filename,
    )

    pages = [
        {
            "page_number": 1,
            "text": ocr_result["text"],
            "extraction_method": "ocr",
            "ocr_provider": ocr_result["provider"],
        }
    ]

    return build_text_result(pages)


# ==========================================================
# PDF PAGE -> IMAGE
# ==========================================================

def render_pdf_page(
    content: bytes,
    page_index: int,
) -> bytes:

    document = None

    try:
        document = pymupdf.open(
            stream=content,
            filetype="pdf",
        )

        page = document.load_page(page_index)

        pixmap = page.get_pixmap(
            dpi=200,
            alpha=False,
        )

        return pixmap.tobytes("png")

    except Exception as error:
        raise TextExtractionError(
            "Failed to convert PDF page into an image."
        ) from error

    finally:
        if document is not None:
            document.close()


# ==========================================================
# OCR PROVIDER ROUTER
# ==========================================================

async def perform_ocr(
    image_bytes: bytes,
    filename: str,
) -> dict:
    """
    Primary OCR:
        OCR.Space

    Fallback OCR:
        Gemini Vision

    Returns:

        {
            "text": "...",
            "provider": "ocr_space"
        }

    or:

        {
            "text": "...",
            "provider": "gemini_vision"
        }
    """

    primary_error = None

    # ------------------------------------------------------
    # Try OCR.Space first
    # ------------------------------------------------------

    if OCR_SPACE_API_KEY:

        try:
            text = await perform_ocr_space(
                image_bytes=image_bytes,
                filename=filename,
            )

            return {
                "text": text,
                "provider": "ocr_space",
            }

        except Exception as error:
            # Do not immediately stop processing.
            #
            # OCR.Space may be:
            # - overloaded
            # - rate limited
            # - temporarily unavailable
            #
            # We will try Gemini Vision instead.

            primary_error = error

    # ------------------------------------------------------
    # Fallback to Gemini Vision
    # ------------------------------------------------------

    if GEMINI_API_KEY:

        try:
            text = await perform_gemini_ocr(
                image_bytes=image_bytes,
                filename=filename,
            )

            return {
                "text": text,
                "provider": "gemini_vision",
            }

        except Exception as error:
            raise TextExtractionError(
                "All OCR providers failed."
            ) from error

    # ------------------------------------------------------
    # No fallback available
    # ------------------------------------------------------

    if primary_error:
        raise TextExtractionError(
            f"OCR.Space failed and no fallback OCR "
            f"provider is configured: {primary_error}"
        )

    raise TextExtractionError(
        "No OCR provider is configured."
    )


# ==========================================================
# OCR.SPACE
# ==========================================================

async def perform_ocr_space(
    image_bytes: bytes,
    filename: str,
) -> str:

    if not OCR_SPACE_API_KEY:
        raise TextExtractionError(
            "OCR.Space API key is not configured."
        )

    content_type = get_image_content_type(
        filename
    )

    files = {
        "file": (
            filename,
            image_bytes,
            content_type,
        )
    }

    data = {
        "language": "eng",
        "isOverlayRequired": "false",
        "OCREngine": "2",
    }

    headers = {
        "apikey": OCR_SPACE_API_KEY,
    }

    try:

        async with httpx.AsyncClient(
            timeout=60.0
        ) as client:

            response = await client.post(
                OCR_SPACE_API_URL,
                files=files,
                data=data,
                headers=headers,
            )

        # --------------------------------------------
        # Detect upstream service errors
        # --------------------------------------------

        if response.status_code != 200:

            raise TextExtractionError(
                f"OCR.Space returned HTTP "
                f"{response.status_code}."
            )

        result = response.json()

    except httpx.RequestError as error:

        raise TextExtractionError(
            f"OCR.Space request failed: "
            f"{type(error).__name__}"
        ) from error

    except ValueError as error:

        raise TextExtractionError(
            "OCR.Space returned invalid JSON."
        ) from error

    return parse_ocr_space_response(
        result
    )


# ==========================================================
# OCR.SPACE RESPONSE PARSER
# ==========================================================

def parse_ocr_space_response(
    result: dict,
) -> str:

    if result.get("IsErroredOnProcessing"):

        error_message = result.get(
            "ErrorMessage",
            "OCR processing failed.",
        )

        if isinstance(error_message, list):

            error_message = " ".join(
                str(message)
                for message in error_message
            )

        raise TextExtractionError(
            str(error_message)
        )

    parsed_results = result.get(
        "ParsedResults",
        [],
    )

    if not parsed_results:

        raise TextExtractionError(
            "OCR.Space returned no parsed results."
        )

    extracted_text = []

    for parsed_page in parsed_results:

        page_text = parsed_page.get(
            "ParsedText",
            "",
        ).strip()

        if page_text:
            extracted_text.append(
                page_text
            )

    final_text = "\n".join(
        extracted_text
    ).strip()

    if not final_text:

        raise TextExtractionError(
            "OCR.Space could not detect readable text."
        )

    return final_text


# ==========================================================
# GEMINI VISION FALLBACK OCR
# ==========================================================

async def perform_gemini_ocr(
    image_bytes: bytes,
    filename: str,
) -> str:

    if not GEMINI_API_KEY:

        raise TextExtractionError(
            "Gemini API key is not configured."
        )

    content_type = get_image_content_type(
        filename
    )

    prompt = """
You are an OCR transcription engine.

Transcribe all visible text from this financial document image.

Rules:
1. Return only text found in the image.
2. Do not summarize.
3. Do not explain.
4. Do not invent or infer missing information.
5. Preserve numbers, decimal values and financial amounts carefully.
6. Preserve line breaks where practical.
7. Include table text, labels and values.
8. If a character is unreadable, do not guess it.
"""

    try:

        async with genai.Client(
            api_key=GEMINI_API_KEY
        ).aio as client:

            response = await client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=content_type,
                    ),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                ),
            )

        text = (
            response.text
            if response.text
            else ""
        ).strip()

        if not text:

            raise TextExtractionError(
                "Gemini Vision returned no OCR text."
            )

        return text

    except TextExtractionError:
        raise

    except Exception as error:

        raise TextExtractionError(
            f"Gemini Vision OCR failed: "
            f"{type(error).__name__}"
        ) from error


# ==========================================================
# IMAGE CONTENT TYPE
# ==========================================================

def get_image_content_type(
    filename: str,
) -> str:

    extension = Path(filename).suffix.lower()

    if extension in {
        ".jpg",
        ".jpeg",
    }:
        return "image/jpeg"

    return "image/png"


# ==========================================================
# BUILD FINAL TEXT RESULT
# ==========================================================

def build_text_result(
    pages: list[dict],
) -> dict:

    combined_parts = []

    for page in pages:

        combined_parts.append(
            f"--- PAGE {page['page_number']} ---\n"
            f"{page['text']}"
        )

    combined_text = "\n\n".join(
        combined_parts
    )

    ocr_used = any(
        page["extraction_method"] == "ocr"
        for page in pages
    )

    fallback_used = any(
        page.get("ocr_provider")
        == "gemini_vision"
        for page in pages
    )

    return {
        "text": combined_text,
        "pages": pages,
        "ocr_used": ocr_used,
        "ocr_fallback_used": fallback_used,
    }