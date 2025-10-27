"""OCR engines for text extraction."""
from core.ocr.engine import OCREngine, OCRMethod
from core.ocr.tesseract_ocr import TesseractOCR
from core.ocr.template_ocr import TemplateOCR

__all__ = [
    'OCREngine',
    'OCRMethod',
    'TesseractOCR',
    'TemplateOCR'
]