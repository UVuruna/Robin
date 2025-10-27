"""
Module: TesseractOCR
Purpose: Tesseract OCR wrapper with optimization for Aviator game text
Version: 2.0

This module provides:
- Tesseract OCR integration with custom configuration
- Image preprocessing for better accuracy
- Whitelist support for specific character sets
- Auto-detection of Tesseract installation
- Fallback strategies for failed reads
"""

import logging
import os
import re
from typing import Optional, Tuple
import numpy as np
from PIL import Image
import pytesseract


class TesseractOCR:
    """
    Tesseract OCR wrapper optimized for game text recognition.

    Features:
    - Custom whitelists for scores, money, player counts
    - Image preprocessing for better accuracy
    - Configurable OEM and PSM modes
    - Auto-detection of Tesseract executable
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize Tesseract OCR.

        Args:
            tesseract_cmd: Path to tesseract executable (auto-detected if None)
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Set Tesseract command
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        else:
            self._auto_detect_tesseract()

        # Verify Tesseract is available
        self._verify_tesseract()

        # Load configuration
        from config.settings import OCR
        self.config = OCR

        # Statistics
        self.stats = {
            "total_reads": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "avg_confidence": 0.0
        }

        self.logger.info("TesseractOCR initialized")

    def _auto_detect_tesseract(self):
        """Auto-detect Tesseract installation path."""
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",  # Linux
            "/usr/local/bin/tesseract",  # macOS
        ]

        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                self.logger.info(f"Auto-detected Tesseract at: {path}")
                return

        self.logger.warning("Could not auto-detect Tesseract. Please specify path manually.")

    def _verify_tesseract(self):
        """Verify Tesseract is available and working."""
        try:
            version = pytesseract.get_tesseract_version()
            self.logger.info(f"Tesseract version: {version}")
        except Exception as e:
            self.logger.error(f"Tesseract not found or not working: {e}")
            raise RuntimeError(
                "Tesseract OCR is not installed or not found. "
                "Download from: https://github.com/UB-Mannheim/tesseract/wiki"
            )

    def _preprocess_image(self, image: np.ndarray, region_type: str = "score") -> Image.Image:
        """
        Preprocess image for better OCR accuracy.

        Args:
            image: Input image as numpy array (BGR from cv2)
            region_type: Type of region ("score", "money", "player_count")

        Returns:
            Preprocessed PIL Image
        """
        # Convert BGR to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            import cv2
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        pil_image = Image.fromarray(image)

        # Apply preprocessing based on region type
        if region_type in ["score", "money", "player_count"]:
            # Convert to grayscale
            pil_image = pil_image.convert('L')

            # Increase contrast (Aviator uses white text on black background)
            # This is already handled by Stylus CSS, but we ensure it here
            import PIL.ImageEnhance
            enhancer = PIL.ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(2.0)  # Increase contrast

        return pil_image

    def _get_tesseract_config(self, region_type: str = "score") -> str:
        """
        Get Tesseract configuration string for specific region type.

        Args:
            region_type: Type of region ("score", "money", "player_count")

        Returns:
            Tesseract config string
        """
        # Base configuration
        oem = self.config.oem
        psm = self.config.psm

        # Get whitelist for this region type
        whitelist = self.config.tesseract_whitelist.get(region_type, "")

        # Build config string
        config_parts = [
            f"--oem {oem}",
            f"--psm {psm}",
        ]

        if whitelist:
            config_parts.append(f"-c tessedit_char_whitelist={whitelist}")

        return " ".join(config_parts)

    def read_text(
        self,
        image: np.ndarray,
        region_type: str = "score",
        preprocess: bool = True
    ) -> Optional[str]:
        """
        Read text from image using Tesseract.

        Args:
            image: Input image as numpy array
            region_type: Type of region for preprocessing and whitelist
            preprocess: Whether to preprocess image

        Returns:
            Extracted text or None if failed

        Example:
            >>> ocr = TesseractOCR()
            >>> text = ocr.read_text(image, region_type="score")
            >>> print(text)  # "123.45"
        """
        self.stats["total_reads"] += 1

        try:
            # Preprocess if enabled
            if preprocess:
                pil_image = self._preprocess_image(image, region_type)
            else:
                pil_image = Image.fromarray(image)

            # Get config for this region type
            config = self._get_tesseract_config(region_type)

            # Perform OCR
            text = pytesseract.image_to_string(pil_image, config=config)

            # Clean up text
            text = text.strip()

            if text:
                self.stats["successful_reads"] += 1
                self.logger.debug(f"OCR read: '{text}' (type: {region_type})")
                return text
            else:
                self.stats["failed_reads"] += 1
                return None

        except Exception as e:
            self.stats["failed_reads"] += 1
            self.logger.error(f"OCR failed: {e}")
            return None

    def read_score(self, image: np.ndarray) -> Optional[float]:
        """
        Read score from image and parse as float.

        Args:
            image: Input image containing score text

        Returns:
            Score as float or None if failed

        Example:
            >>> ocr = TesseractOCR()
            >>> score = ocr.read_score(image)
            >>> print(score)  # 123.45
        """
        text = self.read_text(image, region_type="score")

        if text:
            try:
                # Remove any non-numeric characters except decimal point
                cleaned = re.sub(r'[^\d.]', '', text)

                # Parse as float
                score = float(cleaned)

                # Validate score range (Aviator scores are typically 1.00 - 10000.00)
                if 1.0 <= score <= 10000.0:
                    return score
                else:
                    self.logger.warning(f"Score out of valid range: {score}")
                    return None

            except ValueError:
                self.logger.warning(f"Could not parse score: '{text}'")
                return None

        return None

    def read_money(self, image: np.ndarray) -> Optional[float]:
        """
        Read money amount from image and parse as float.

        Args:
            image: Input image containing money text

        Returns:
            Money amount as float or None if failed

        Example:
            >>> ocr = TesseractOCR()
            >>> money = ocr.read_money(image)
            >>> print(money)  # 12345.67
        """
        text = self.read_text(image, region_type="money")

        if text:
            try:
                # Remove commas and any non-numeric characters except decimal point
                cleaned = re.sub(r'[^\d.]', '', text)

                # Parse as float
                money = float(cleaned)

                # Validate money range (reasonable amounts)
                if 0.0 <= money <= 1000000.0:
                    return money
                else:
                    self.logger.warning(f"Money out of valid range: {money}")
                    return None

            except ValueError:
                self.logger.warning(f"Could not parse money: '{text}'")
                return None

        return None

    def read_player_count(self, image: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Read player count from image (format: "123/456").

        Args:
            image: Input image containing player count text

        Returns:
            Tuple of (current_players, total_players) or None if failed

        Example:
            >>> ocr = TesseractOCR()
            >>> counts = ocr.read_player_count(image)
            >>> print(counts)  # (123, 456)
        """
        text = self.read_text(image, region_type="player_count")

        if text:
            try:
                # Expected format: "123/456" or "123 / 456"
                match = re.search(r'(\d+)\s*/\s*(\d+)', text)

                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))

                    # Validate counts
                    if 0 <= current <= total and total <= 100000:
                        return (current, total)
                    else:
                        self.logger.warning(f"Player counts out of valid range: {current}/{total}")
                        return None

            except (ValueError, AttributeError):
                self.logger.warning(f"Could not parse player count: '{text}'")
                return None

        return None

    def read_with_confidence(
        self,
        image: np.ndarray,
        region_type: str = "score"
    ) -> Tuple[Optional[str], float]:
        """
        Read text with confidence score.

        Args:
            image: Input image
            region_type: Type of region

        Returns:
            Tuple of (text, confidence) where confidence is 0-100

        Example:
            >>> ocr = TesseractOCR()
            >>> text, conf = ocr.read_with_confidence(image)
            >>> print(f"Text: {text}, Confidence: {conf}%")
        """
        try:
            # Preprocess
            pil_image = self._preprocess_image(image, region_type)

            # Get config
            config = self._get_tesseract_config(region_type)

            # Get detailed data
            data = pytesseract.image_to_data(
                pil_image,
                config=config,
                output_type=pytesseract.Output.DICT
            )

            # Extract text and confidence
            confidences = [conf for conf in data['conf'] if conf != -1]
            texts = [text for text in data['text'] if text.strip()]

            if texts and confidences:
                text = " ".join(texts).strip()
                avg_confidence = sum(confidences) / len(confidences)

                # Update stats
                self.stats["avg_confidence"] = (
                    (self.stats["avg_confidence"] * self.stats["successful_reads"] + avg_confidence)
                    / (self.stats["successful_reads"] + 1)
                )

                return text, avg_confidence
            else:
                return None, 0.0

        except Exception as e:
            self.logger.error(f"OCR with confidence failed: {e}")
            return None, 0.0

    def get_stats(self) -> dict:
        """
        Get OCR statistics.

        Returns:
            Dictionary with statistics
        """
        success_rate = 0.0
        if self.stats["total_reads"] > 0:
            success_rate = (self.stats["successful_reads"] / self.stats["total_reads"]) * 100

        return {
            **self.stats,
            "success_rate": f"{success_rate:.2f}%",
            "tesseract_cmd": pytesseract.pytesseract.tesseract_cmd
        }

    def cleanup(self):
        """Cleanup resources."""
        self.logger.info(f"TesseractOCR cleanup - Stats: {self.get_stats()}")


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    ocr = TesseractOCR()
    print("Tesseract OCR initialized successfully")
    print(f"Stats: {ocr.get_stats()}")
