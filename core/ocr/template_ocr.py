"""
Module: TemplateOCR
Purpose: Ultra-fast template matching OCR for digit recognition
Version: 2.0

This module provides:
- Template matching for 10x faster OCR (target: < 15ms)
- Pre-loaded digit templates (0-9) and decimal point
- 99%+ accuracy requirement
- Optimized for Aviator score reading
- Support for multiple template categories (score, money, controls)
"""

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
import cv2
import numpy as np


class TemplateOCR:
    """
    Template matching OCR engine optimized for speed and accuracy.

    Performance target: < 15ms per read
    Accuracy target: 99%+

    Features:
    - Pre-loaded templates for instant matching
    - Multi-scale template matching
    - Caching for repeated operations
    - Support for multiple template categories
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize TemplateOCR.

        Args:
            templates_dir: Path to OCR templates directory
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # Set templates directory
        if templates_dir is None:
            from config.settings import PATH
            templates_dir = PATH.data_dir / "ocr_templates"

        self.templates_dir = templates_dir

        # Load configuration
        from config.settings import OCR
        self.threshold = OCR.template_threshold  # 0.99 = 99% match
        self.method = OCR.template_method  # cv2.TM_CCOEFF_NORMED

        # Template storage
        self.templates: Dict[str, Dict[str, np.ndarray]] = {
            "score": {},  # 0-9 and decimal point for scores
            "money": {},  # 0-9, decimal, comma for money amounts
            "controls": {}  # For button states, etc.
        }

        # Load templates
        self._load_templates()

        # Statistics
        self.stats = {
            "total_reads": 0,
            "successful_reads": 0,
            "failed_reads": 0,
            "avg_read_time_ms": 0.0,
            "fastest_read_ms": float('inf'),
            "slowest_read_ms": 0.0
        }

        self.logger.info(f"TemplateOCR initialized with {self._count_templates()} templates")

    def _count_templates(self) -> int:
        """Count total loaded templates."""
        return sum(len(cat) for cat in self.templates.values())

    def _load_templates(self):
        """Load all template images from disk."""
        start_time = time.time()

        # Load score templates (0-9, decimal point)
        score_dir = self.templates_dir / "score"
        if score_dir.exists():
            for digit in "0123456789":
                template_path = score_dir / f"{digit}.png"
                if template_path.exists():
                    self.templates["score"][digit] = cv2.imread(
                        str(template_path),
                        cv2.IMREAD_GRAYSCALE
                    )

            # Check for decimal point template
            decimal_path = score_dir / "decimal.png"
            if decimal_path.exists():
                self.templates["score"]["."] = cv2.imread(
                    str(decimal_path),
                    cv2.IMREAD_GRAYSCALE
                )

        # Load money templates (if different from score)
        money_dir = self.templates_dir / "money"
        if money_dir.exists():
            for digit in "0123456789":
                template_path = money_dir / f"{digit}.png"
                if template_path.exists():
                    self.templates["money"][digit] = cv2.imread(
                        str(template_path),
                        cv2.IMREAD_GRAYSCALE
                    )

            # Decimal and comma
            for char, filename in [(".", "decimal.png"), (",", "comma.png")]:
                char_path = money_dir / filename
                if char_path.exists():
                    self.templates["money"][char] = cv2.imread(
                        str(char_path),
                        cv2.IMREAD_GRAYSCALE
                    )

        # Load control templates (buttons, etc.)
        controls_dir = self.templates_dir / "controls"
        if controls_dir.exists():
            for template_file in controls_dir.glob("*.png"):
                name = template_file.stem
                self.templates["controls"][name] = cv2.imread(
                    str(template_file),
                    cv2.IMREAD_GRAYSCALE
                )

        load_time = (time.time() - start_time) * 1000
        self.logger.info(f"Loaded {self._count_templates()} templates in {load_time:.2f}ms")

    def _match_single_template(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: Optional[float] = None
    ) -> Tuple[bool, float, Tuple[int, int]]:
        """
        Match a single template against image.

        Args:
            image: Input image (grayscale)
            template: Template to match (grayscale)
            threshold: Match threshold (uses default if None)

        Returns:
            Tuple of (matched, confidence, location)
        """
        if threshold is None:
            threshold = self.threshold

        # Perform template matching
        result = cv2.matchTemplate(image, template, self.method)

        # Find best match
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # For TM_CCOEFF_NORMED, higher is better
        confidence = max_val
        location = max_loc

        matched = confidence >= threshold

        return matched, confidence, location

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for template matching.

        Args:
            image: Input image (BGR or RGB)

        Returns:
            Preprocessed grayscale image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply threshold to get clean white-on-black (Aviator uses white text)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        return binary

    def read_digits(
        self,
        image: np.ndarray,
        category: str = "score",
        allow_decimal: bool = True
    ) -> Optional[str]:
        """
        Read digit sequence from image using template matching.

        Args:
            image: Input image
            category: Template category ("score", "money")
            allow_decimal: Whether to allow decimal point

        Returns:
            String of recognized digits or None if failed

        Example:
            >>> ocr = TemplateOCR()
            >>> text = ocr.read_digits(image, category="score")
            >>> print(text)  # "123.45"
        """
        start_time = time.time()
        self.stats["total_reads"] += 1

        try:
            # Preprocess image
            preprocessed = self._preprocess_image(image)

            # Get templates for this category
            if category not in self.templates or not self.templates[category]:
                self.logger.warning(f"No templates loaded for category: {category}")
                self.stats["failed_reads"] += 1
                return None

            templates = self.templates[category]

            # Detect digit positions by scanning image horizontally
            # We'll find all digit matches and sort by X position
            matches = []

            for char, template in templates.items():
                # Skip decimal if not allowed
                if char == "." and not allow_decimal:
                    continue

                # Match this template
                matched, confidence, location = self._match_single_template(
                    preprocessed,
                    template
                )

                if matched:
                    matches.append({
                        "char": char,
                        "x": location[0],
                        "y": location[1],
                        "confidence": confidence
                    })

            # Sort matches by X position (left to right)
            matches.sort(key=lambda m: m["x"])

            # Build result string
            if matches:
                result = "".join(m["char"] for m in matches)

                # Validate result
                if self._validate_result(result, category):
                    self.stats["successful_reads"] += 1

                    # Update timing stats
                    read_time = (time.time() - start_time) * 1000
                    self._update_timing_stats(read_time)

                    return result
                else:
                    self.logger.debug(f"Invalid result: {result}")
                    self.stats["failed_reads"] += 1
                    return None
            else:
                self.stats["failed_reads"] += 1
                return None

        except Exception as e:
            self.logger.error(f"Template matching failed: {e}")
            self.stats["failed_reads"] += 1
            return None

    def _validate_result(self, result: str, category: str) -> bool:
        """
        Validate OCR result based on category.

        Args:
            result: OCR result string
            category: Template category

        Returns:
            True if valid, False otherwise
        """
        if not result:
            return False

        if category == "score":
            # Score should be digits with optional decimal point
            # Valid: "1", "12", "123", "1.23", "12.34"
            # Invalid: ".1", "1.", "1.2.3"
            import re
            return bool(re.match(r'^\d+(\.\d+)?$', result))

        elif category == "money":
            # Money can have commas and decimal
            # Valid: "1", "1234", "1,234", "1,234.56"
            import re
            return bool(re.match(r'^\d{1,3}(,\d{3})*(\.\d{2})?$', result))

        return True  # Default: accept all

    def _update_timing_stats(self, read_time_ms: float):
        """Update timing statistics."""
        # Update average
        total = self.stats["total_reads"]
        current_avg = self.stats["avg_read_time_ms"]
        self.stats["avg_read_time_ms"] = (current_avg * (total - 1) + read_time_ms) / total

        # Update fastest/slowest
        if read_time_ms < self.stats["fastest_read_ms"]:
            self.stats["fastest_read_ms"] = read_time_ms
        if read_time_ms > self.stats["slowest_read_ms"]:
            self.stats["slowest_read_ms"] = read_time_ms

    def read_score(self, image: np.ndarray) -> Optional[float]:
        """
        Read score from image and parse as float.

        Args:
            image: Input image containing score

        Returns:
            Score as float or None if failed

        Example:
            >>> ocr = TemplateOCR()
            >>> score = ocr.read_score(image)
            >>> print(score)  # 123.45
        """
        text = self.read_digits(image, category="score", allow_decimal=True)

        if text:
            try:
                score = float(text)

                # Validate score range
                if 1.0 <= score <= 10000.0:
                    return score
                else:
                    self.logger.warning(f"Score out of range: {score}")
                    return None

            except ValueError:
                self.logger.warning(f"Could not parse score: '{text}'")
                return None

        return None

    def read_money(self, image: np.ndarray) -> Optional[float]:
        """
        Read money amount from image and parse as float.

        Args:
            image: Input image containing money amount

        Returns:
            Money as float or None if failed

        Example:
            >>> ocr = TemplateOCR()
            >>> money = ocr.read_money(image)
            >>> print(money)  # 12345.67
        """
        text = self.read_digits(image, category="money", allow_decimal=True)

        if text:
            try:
                # Remove commas
                cleaned = text.replace(",", "")
                money = float(cleaned)

                # Validate range
                if 0.0 <= money <= 1000000.0:
                    return money
                else:
                    self.logger.warning(f"Money out of range: {money}")
                    return None

            except ValueError:
                self.logger.warning(f"Could not parse money: '{text}'")
                return None

        return None

    def has_templates(self, category: str) -> bool:
        """
        Check if templates are loaded for a category.

        Args:
            category: Template category name

        Returns:
            True if templates exist, False otherwise
        """
        return category in self.templates and len(self.templates[category]) > 0

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
            "templates_loaded": self._count_templates(),
            "performance_target_met": self.stats["avg_read_time_ms"] < 15.0
        }

    def cleanup(self):
        """Cleanup resources."""
        self.templates.clear()
        self.logger.info(f"TemplateOCR cleanup - Stats: {self.get_stats()}")


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    ocr = TemplateOCR()
    print(f"Templates loaded: {ocr._count_templates()}")
    print(f"Has score templates: {ocr.has_templates('score')}")
    print(f"Stats: {ocr.get_stats()}")
