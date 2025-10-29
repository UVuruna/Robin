"""OCR engines for text extraction."""
from core.ocr.engine import OCREngine
from config.settings import OCRMethod
from core.ocr.tesseract_ocr import TesseractOCR
from core.ocr.template_ocr import TemplateOCR
from core.ocr.cnn_ocr import CNNOCRReader

__all__ = [
    'OCREngine',
    'OCRMethod',
    'TesseractOCR',
    'TemplateOCR',
    'CNNOCRReader'
]