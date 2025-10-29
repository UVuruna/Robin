"""Core functionality for AVIATOR system."""
from core.communication.event_bus import EventBus, EventPublisher, EventSubscriber
from core.communication.shared_state import SharedGameState, get_shared_state
from core.capture.screen_capture import ScreenCapture
from core.capture.region_manager import RegionManager, get_region_manager
from core.ocr.engine import OCREngine
from config.settings import OCRMethod
from core.ocr.tesseract_ocr import TesseractOCR
from core.ocr.template_ocr import TemplateOCR
from core.ocr.cnn_ocr import CNNOCRReader
from core.input.transaction_controller import TransactionController
from core.input.action_queue import ActionQueue

__all__ = [
    'EventBus',
    'EventPublisher',
    'EventSubscriber',
    'SharedGameState',
    'get_shared_state',
    'ScreenCapture',
    'RegionManager',
    'get_region_manager',
    'OCREngine',
    'OCRMethod',
    'TesseractOCR',
    'TemplateOCR',
    'CNNOCRReader',
    'TransactionController',
    'ActionQueue'
]