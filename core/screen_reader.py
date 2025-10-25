# core/screen_reader.py
# VERSION: 8.1 - SIMPLE PREPROCESSING
# CHANGES: Added simple preprocessing from TESTING.py (grayscale + invert + Otsu)

import mss
import numpy as np
import pytesseract
import cv2
import re
from typing import Optional, Dict, Tuple
from utils.logger import AviatorLogger
from pathlib import Path
from config.ocr_config import get_tesseract_config


class ScreenReader:
    """
    Screen reader with simple preprocessing.
    Uses grayscale + invert + Otsu threshold from TESTING.py.
    """

    _tesseract_configured = False

    @classmethod
    def _configure_tesseract(cls):
        """Configure tesseract path once per process."""
        if cls._tesseract_configured:
            return

        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\vurun\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            "tesseract",
        ]

        import shutil
        if shutil.which("tesseract"):
            pytesseract.pytesseract.tesseract_cmd = "tesseract"
            cls._tesseract_configured = True
            return

        for path in possible_paths:
            if path == "tesseract":
                continue
            if Path(path).exists():
                pytesseract.pytesseract.tesseract_cmd = path
                cls._tesseract_configured = True
                return

        cls._tesseract_configured = True

    def __init__(self, region: Dict[str, int], custom_config: Optional[str] = None):
        """
        Initialize screen reader.

        Args:
            region: Dict with keys 'left', 'top', 'width', 'height'
            custom_config: Optional custom tesseract config
        """
        self._configure_tesseract()

        self.region = region
        self.custom_config = custom_config
        self.logger = AviatorLogger.get_logger("ScreenReader")
        self._sct = None
        self._last_image = None

    def capture_image(self) -> np.ndarray:
        """Capture screen region as numpy array (BGR)."""
        if self._sct is None:
            self._sct = mss.mss()

        monitor = {
            "left": self.region["left"],
            "top": self.region["top"],
            "width": self.region["width"],
            "height": self.region["height"],
        }

        screenshot = self._sct.grab(monitor)
        img = np.array(screenshot)[:, :, :3]
        self._last_image = img.copy()

        return img

    def _simple_preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Simple preprocessing from TESTING.py.
        
        Steps:
        1. Convert to grayscale
        2. Invert (white text on dark bg)
        3. Otsu's threshold
        
        Args:
            img: BGR image
            
        Returns:
            Binary image
        """
        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Invert
        gray = cv2.bitwise_not(gray)
        
        # Otsu threshold
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary

    def read_text_raw(self, psm: int = 7) -> str:
        """
        Read raw text using Tesseract.

        Args:
            psm: Page segmentation mode (7=single line, 6=block)

        Returns:
            Raw OCR text
        """
        try:
            img = self.capture_image()

            # Use custom config if provided
            if self.custom_config:
                config = self.custom_config
            else:
                config = f"--oem 3 --psm {psm}"
            
            # Convert BGR to RGB for pytesseract
            img_rgb = img[:, :, ::-1]
            
            text = pytesseract.image_to_string(img_rgb, config=config)

            return text.strip()

        except Exception as e:
            self.logger.error(f"OCR error: {e}")
            return ""

    def _clean_text(self, text: str) -> str:
        """Clean OCR text with common character substitutions."""
        text = text.replace("I", "1")
        text = text.replace("l", "1")
        text = text.replace("O", "0")
        text = text.replace(" ", "")
        return text.strip()

    def read_score(self) -> Optional[float]:
        """
        Read score with simple preprocessing.
        Uses whitelist config + simple preprocessing.
        
        Returns:
            Float score or None
        """
        try:
            img = self.capture_image()
            
            # Simple preprocessing
            binary = self._simple_preprocess(img)
            
            # Get optimized config
            if not self.custom_config:
                config = get_tesseract_config("score")
            else:
                config = self.custom_config
            
            text = pytesseract.image_to_string(binary, config=config).strip()
            text = self._clean_text(text)

            # Remove 'x' suffix
            text = text.replace("x", "").replace("X", "")
            text = text.replace(",", "")

            # Parse float
            score = float(text)

            if score >= 1:
                return score
            else:
                self.logger.warning(f"Score out of range: {score}")
                return None

        except ValueError:
            self.logger.warning(f"Failed to parse score: '{text}'")
            return None
        except Exception as e:
            self.logger.error(f"Error reading score: {e}")
            return None

    def read_money(self) -> Optional[float]:
        """
        Read money with simple preprocessing.
        
        Returns:
            Float money value or None
        """
        try:
            img = self.capture_image()
            
            # Simple preprocessing
            binary = self._simple_preprocess(img)
            
            if not self.custom_config:
                config = get_tesseract_config("money")
            else:
                config = self.custom_config
            
            text = pytesseract.image_to_string(binary, config=config).strip()
            text = self._clean_text(text)
            text = text.replace(",", "")

            money = float(text)

            if money >= 0:
                return money
            else:
                self.logger.warning(f"Negative money: {money}")
                return None

        except ValueError:
            self.logger.warning(f"Failed to parse money: '{text}'")
            return None
        except Exception as e:
            self.logger.error(f"Error reading money: {e}")
            return None

    def read_player_count(self) -> Optional[Tuple[int, int]]:
        """
        Read player count with simple preprocessing.
        
        Returns:
            Tuple (left_players, total_players) or None
        """
        try:
            img = self.capture_image()
            
            # Simple preprocessing
            binary = self._simple_preprocess(img)
            
            if not self.custom_config:
                config = get_tesseract_config("player_count")
            else:
                config = self.custom_config
            
            text = pytesseract.image_to_string(binary, config=config).strip()
            text = self._clean_text(text)

            # Parse format: "234/567"
            match = re.match(r"(\d+)/(\d+)", text)

            if match:
                left = int(match.group(1))
                total = int(match.group(2))

                if 0 <= left <= total:
                    return (left, total)
                else:
                    self.logger.warning(f"Invalid count: {left}/{total}")
                    return None
            else:
                self.logger.warning(f"Failed to match count format: '{text}'")
                return None

        except Exception as e:
            self.logger.error(f"Error reading player count: {e}")
            return None

    def read_text(self) -> str:
        """Read raw text (for generic use cases)."""
        return self.read_text_raw(psm=7)

    def save_last_capture(self, filename: str) -> bool:
        """Save last captured image for debugging."""
        try:
            if self._last_image is not None:
                cv2.imwrite(filename, self._last_image)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
            return False

    def close(self):
        """Clean up resources."""
        if self._sct:
            self._sct.close()
            self._sct = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.close()