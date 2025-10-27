"""Test suite for AVIATOR project."""
from tests.ml_phase_accuracy import test_phase_accuracy
from tests.ml_phase_performance import test_phase_performance
from tests.ocr_accuracy import test_ocr_accuracy
from tests.ocr_performance import test_ocr_performance

__all__ = [
    'test_phase_accuracy',
    'test_phase_performance', 
    'test_ocr_accuracy',
    'test_ocr_performance'
]