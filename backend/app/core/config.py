import os

from dotenv import load_dotenv


load_dotenv()


OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.7-flash",
)
# ==========================================================
# SETTINGS COMPATIBILITY OBJECT
# ==========================================================

import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """
    Central application settings.

    This object is used by services such as
    extraction_service.py while keeping compatibility
    with any existing configuration constants.
    """

    OCR_SPACE_API_KEY = os.getenv(
        "OCR_SPACE_API_KEY"
    )

    GEMINI_API_KEY = os.getenv(
        "GEMINI_API_KEY"
    )

    GEMINI_MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )


settings = Settings()