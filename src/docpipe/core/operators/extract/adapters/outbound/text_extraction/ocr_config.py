"""Shared OCR configuration model used by both docling_library and docling_serve adapters."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OcrEngineKind = Literal[
    "auto", "easyocr", "tesserocr", "tesseract", "rapidocr", "ocrmac", "kserve_v2_ocr", "nemotron-ocr"
]

OcrModeKind = Literal["full_page", "layout_regions", "pdf_aware_layout_regions", "default"]


class OcrConfig(BaseModel):
    """OCR configuration block for the docling_library and docling_serve providers.

    Provide this block inside ``text_extraction.provider_config.ocr`` to control OCR
    behaviour. Omitting the block entirely uses docling-pipelines defaults (RapidOCR engine,
    OCR enabled, default mode).
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True,
        description="Enable OCR processing. Set to false to skip OCR entirely.",
    )
    engine: OcrEngineKind = Field(
        default="rapidocr",
        description=(
            "OCR engine to use. 'rapidocr' is the docling-pipelines default for first-run portability. "
            "Use 'auto' only when you want Docling to select an installed backend at runtime. "
            "Valid values: 'auto', 'easyocr', 'tesserocr', 'tesseract', 'rapidocr', 'ocrmac', "
            "'kserve_v2_ocr', 'nemotron-ocr'."
        ),
    )
    mode: OcrModeKind = Field(
        default="default",
        description=(
            "OCR scanning mode. 'default' uses Docling's automatic selection. "
            "'pdf_aware_layout_regions' skips regions that already have a PDF text layer "
            "and is the most efficient choice for mixed PDFs. "
            "Valid values: 'full_page', 'layout_regions', 'pdf_aware_layout_regions', 'default'."
        ),
    )
    engine_options: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Engine-specific parameters passed directly to the Docling OCR options class. "
            "Keys and values depend on the chosen engine. "
            "Examples — easyocr: {'lang': ['en', 'fr'], 'use_gpu': true, 'confidence_threshold': 0.5}; "
            "tesseract/tesserocr: {'lang': ['eng', 'fra'], 'psm': 3}; "
            "rapidocr: {'lang': ['en'], 'backend': 'onnxruntime', 'text_score': 0.5}; "
            "ocrmac: {'lang': ['en-US'], 'recognition': 'accurate'}."
        ),
    )
