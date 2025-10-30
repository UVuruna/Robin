# core/ocr/cnn_ocr.py
# VERSION: 2.0 - CNN OCR with LAZY TensorFlow Import
# PURPOSE: CNN-based OCR for score/money reading using trained models

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Optional, Dict
import pickle

# LAZY IMPORT: TensorFlow/Keras loaded ONLY when CNN models are actually used
TENSORFLOW_AVAILABLE = None  # None = not checked yet, True/False after check
tf = None
keras = None


def _ensure_tensorflow():
    """
    Lazy import TensorFlow - only loads when CNN OCR is actually used.

    Returns:
        True if TensorFlow is available, False otherwise
    """
    global TENSORFLOW_AVAILABLE, tf, keras

    if TENSORFLOW_AVAILABLE is None:
        try:
            import tensorflow as tf_module
            from tensorflow import keras as keras_module
            tf = tf_module
            keras = keras_module
            TENSORFLOW_AVAILABLE = True

            # Suppress TensorFlow warnings
            tf_module.get_logger().setLevel('ERROR')

        except ImportError:
            TENSORFLOW_AVAILABLE = False
            tf = None
            keras = None

    return TENSORFLOW_AVAILABLE


class CNNOCRReader:
    """
    CNN-based OCR reader for Aviator game regions.

    Features:
    - Trained CNN models for score/money recognition
    - Preprocesses images to model input size
    - Returns same format as Tesseract (string)
    - Lazy model loading (only when first used)
    """

    def __init__(self, model_paths: Dict[str, Path]):
        """
        Initialize CNN OCR Reader (TensorFlow NOT imported yet).

        Args:
            model_paths: Dictionary mapping region type to model path
                         Example: {"score": Path("data/models/score_cnn.h5")}
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_paths = model_paths
        self.models: Dict[str, any] = {}  # Lazy-loaded models
        self.loaded = False

        # NOTE: TensorFlow is NOT imported here! Will be loaded when first model is needed.
        self.logger.info(f"CNN OCR Reader initialized with {len(model_paths)} model paths")

    def _load_model(self, region_type: str) -> bool:
        """
        Lazy load CNN model for specific region type.

        This is where TensorFlow is actually imported (first time only).

        Args:
            region_type: "score", "money", etc.

        Returns:
            True if model loaded successfully
        """
        # LAZY IMPORT: Load TensorFlow NOW (only first time)
        if not _ensure_tensorflow():
            self.logger.error("Cannot load model - TensorFlow not available")
            return False

        if region_type in self.models:
            return True  # Already loaded

        model_path = self.model_paths.get(region_type)
        if not model_path or not model_path.exists():
            self.logger.error(f"Model not found for '{region_type}': {model_path}")
            return False

        try:
            # Load Keras model
            model = keras.models.load_model(str(model_path), compile=False)
            self.models[region_type] = model
            self.logger.info(f"Loaded CNN model for '{region_type}': {model_path.name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load model for '{region_type}': {e}")
            return False

    def _preprocess_image(self, img: np.ndarray, target_size: tuple = (64, 256)) -> np.ndarray:
        """
        Preprocess image for CNN model input.

        Args:
            img: Input image (BGR or grayscale)
            target_size: Target size (height, width) for model

        Returns:
            Preprocessed image ready for model
        """
        # Convert to grayscale if needed
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Resize to model input size
        img_resized = cv2.resize(img, (target_size[1], target_size[0]))

        # Normalize to [0, 1]
        img_normalized = img_resized.astype(np.float32) / 255.0

        # Add channel dimension (H, W) -> (H, W, 1)
        img_with_channel = np.expand_dims(img_normalized, axis=-1)

        # Add batch dimension (H, W, 1) -> (1, H, W, 1)
        img_batch = np.expand_dims(img_with_channel, axis=0)

        return img_batch

    def _postprocess_prediction(self, prediction: np.ndarray, region_type: str) -> Optional[str]:
        """
        Convert model prediction to string output.

        Args:
            prediction: Model output (typically softmax probabilities)
            region_type: "score", "money", etc.

        Returns:
            String result (e.g., "1.52", "12.34") or None
        """
        # This is a PLACEHOLDER - actual implementation depends on model architecture
        # Common approaches:
        # 1. CTC decoding for sequence models
        # 2. Argmax + character mapping for classification models
        # 3. Multi-digit prediction with position-based classifiers

        # EXAMPLE for classification-based model (10 digits + dot):
        # Assuming model outputs (N, 11) where 11 = [0-9, '.']
        # and we decode position-by-position

        try:
            # Get character classes (argmax)
            char_indices = np.argmax(prediction, axis=-1)

            # Map indices to characters
            # Character set: ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.']
            char_map = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.']

            result = ""
            for idx in char_indices[0]:  # Remove batch dimension
                if idx < len(char_map):
                    result += char_map[idx]

            # Clean up result
            result = result.strip()

            # Validate format
            if region_type == "score":
                # Score format: digits with optional dot (e.g., "1.52", "12.34")
                if not result or not any(c.isdigit() for c in result):
                    return None

            return result if result else None

        except Exception as e:
            self.logger.error(f"Postprocessing failed: {e}")
            return None

    def read_score(self, img: np.ndarray) -> Optional[str]:
        """
        Read score from image using CNN.

        Args:
            img: Screenshot of score region

        Returns:
            Score string (e.g., "1.52", "12.34") or None
        """
        return self._read_region(img, "score")

    def read_money(self, img: np.ndarray) -> Optional[str]:
        """
        Read money amount from image using CNN.

        Args:
            img: Screenshot of money region

        Returns:
            Money string (e.g., "1234.56") or None
        """
        return self._read_region(img, "money")

    def _read_region(self, img: np.ndarray, region_type: str) -> Optional[str]:
        """
        Generic region reading with CNN.

        Args:
            img: Input image
            region_type: "score", "money", etc.

        Returns:
            OCR result string or None
        """
        # Load model if not already loaded
        if not self._load_model(region_type):
            self.logger.error(f"Cannot read '{region_type}' - model not loaded")
            return None

        try:
            # Preprocess image
            img_preprocessed = self._preprocess_image(img)

            # Run prediction
            model = self.models[region_type]
            prediction = model.predict(img_preprocessed, verbose=0)

            # Postprocess to string
            result = self._postprocess_prediction(prediction, region_type)

            return result

        except Exception as e:
            self.logger.error(f"CNN OCR failed for '{region_type}': {e}")
            return None

    def get_stats(self) -> Dict[str, any]:
        """
        Get OCR statistics.

        Returns:
            Dictionary with stats
        """
        return {
            'models_loaded': len(self.models),
            'model_types': list(self.models.keys()),
            'tensorflow_available': TENSORFLOW_AVAILABLE
        }


# Utility function for backward compatibility
def create_cnn_reader(score_model_path: Path, money_model_path: Path) -> CNNOCRReader:
    """
    Factory function to create CNN reader with standard model paths.

    Args:
        score_model_path: Path to score CNN model (.h5 or .pkl)
        money_model_path: Path to money CNN model

    Returns:
        CNNOCRReader instance
    """
    model_paths = {
        "score": score_model_path,
        "money": money_model_path
    }
    return CNNOCRReader(model_paths)
