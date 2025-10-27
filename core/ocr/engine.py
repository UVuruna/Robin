# core/ocr/engine.py
# VERSION: 1.0 - COMPLETE
# PURPOSE: Glavni OCR engine sa multiple strategijama

import cv2
import numpy as np
import pytesseract
import logging
import time
from typing import Optional, Dict, Any
from pathlib import Path
from enum import IntEnum

from config import GamePhase, OCRConfig

class OCRMethod(IntEnum):
    """Available OCR methods."""
    TESSERACT = 1
    TEMPLATE = 2
    CNN = 3  # Future

class OCREngine:
    """
    Glavni OCR engine koji kombinuje različite metode.
    Automatski bira najbolju metodu za svaki tip podatka.
    """
    
    def __init__(self, method: OCRMethod = OCRMethod.TESSERACT):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.method = method
        
        # Template matching setup
        self.templates_dir = Path("data/ocr_templates")
        self.digit_templates: Dict[str, np.ndarray] = {}
        self.template_ready = False
        
        # OCR configs
        self.ocr_configs = OCR.tesseract_whitelist
        
        # Load templates if using template method
        if method == OCRMethod.TEMPLATE:
            self._load_templates()
        
        # Performance tracking
        self.read_times = []
        self.accuracy_scores = []
        
        self.logger.info(f"Initialized with method: {method.name}")
    
    def _load_templates(self):
        """Load digit templates for template matching."""
        templates_path = self.templates_dir / "score"
        
        if not templates_path.exists():
            self.logger.warning(f"Templates directory not found: {templates_path}")
            return
        
        # Load digit templates (0-9 and .)
        for digit in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'dot']:
            template_file = templates_path / f"{digit}.png"
            if template_file.exists():
                template = cv2.imread(str(template_file), cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    self.digit_templates[digit] = template
                    self.logger.debug(f"Loaded template for '{digit}'")
        
        self.template_ready = len(self.digit_templates) >= 10
        if self.template_ready:
            self.logger.info(f"Loaded {len(self.digit_templates)} templates")
        else:
            self.logger.warning("Not enough templates for template matching")
    
    def read_score(self, img: np.ndarray) -> Optional[str]:
        """
        Read score from image.
        
        Args:
            img: Screenshot of score region
            
        Returns:
            Score string (e.g., "1.52", "12.34") or None
        """
        start_time = time.perf_counter()
        result = None
        
        try:
            if self.method == OCRMethod.TEMPLATE and self.template_ready:
                result = self._read_with_templates(img, "score")
            else:
                result = self._read_with_tesseract(img, "score")
            
            # Track performance
            read_time = time.perf_counter() - start_time
            self.read_times.append(read_time)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error reading score: {e}")
            return None
    
    def read_money(self, img: np.ndarray) -> Optional[str]:
        """
        Read money value from image.
        
        Args:
            img: Screenshot of money region
            
        Returns:
            Money string (e.g., "1,234.56") or None
        """
        try:
            if self.method == OCRMethod.TEMPLATE and self.template_ready:
                result = self._read_with_templates(img, "money")
            else:
                result = self._read_with_tesseract(img, "money")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error reading money: {e}")
            return None
    
    def read_player_count(self, img: np.ndarray) -> Optional[str]:
        """
        Read player count from image.
        
        Args:
            img: Screenshot of player count region
            
        Returns:
            Count string (e.g., "123/456") or None
        """
        try:
            result = self._read_with_tesseract(img, "player_count")
            return result
            
        except Exception as e:
            self.logger.error(f"Error reading player count: {e}")
            return None
    
    def detect_phase(self, img: np.ndarray) -> int:
        """
        Detect game phase from image using RGB analysis.
        
        Args:
            img: Screenshot of phase region
            
        Returns:
            GamePhase value
        """
        try:
            # Calculate average RGB
            avg_color = cv2.mean(img)[:3]  # BGR format
            r, g, b = avg_color[2], avg_color[1], avg_color[0]
            
            # Simple phase detection based on color dominance
            # These thresholds need calibration based on actual data
            
            # BLACK/DARK = LOADING (R<10, G<10, B<10)
            if r < 10 and g < 10 and b < 10:
                return GamePhase.LOADING
            
            # RED DOMINANT = ENDED (R>100, R>G+30, R>B+30)
            if r > 100 and r > g + 30 and r > b + 30:
                return GamePhase.ENDED
            
            # GREEN DOMINANT = BETTING (G>100, G>R+20)
            if g > 100 and g > r + 20:
                return GamePhase.BETTING
            
            # CYAN/BLUE = SCORE phases
            if b > 100:
                # Use brightness to distinguish score levels
                brightness = (r + g + b) / 3
                
                if brightness < 120:
                    return GamePhase.SCORE_LOW
                elif brightness < 160:
                    return GamePhase.SCORE_MID
                else:
                    return GamePhase.SCORE_HIGH
            
            # Default to START
            return GamePhase.START
            
        except Exception as e:
            self.logger.error(f"Error detecting phase: {e}")
            return GamePhase.ENDED
    
    def _read_with_tesseract(self, img: np.ndarray, data_type: str) -> Optional[str]:
        """
        Read text using Tesseract OCR.
        
        Args:
            img: Input image
            data_type: Type of data ('score', 'money', 'player_count')
            
        Returns:
            Extracted text or None
        """
        try:
            # Preprocess
            processed = self._preprocess_image(img, data_type)
            
            # Get whitelist for this data type
            whitelist = self.ocr_configs.get(data_type, "")
            
            # Tesseract config
            config = f'--oem {OCR.oem} --psm {OCR.psm}'
            if whitelist:
                config += f' -c tessedit_char_whitelist={whitelist}'
            
            # OCR
            text = pytesseract.image_to_string(processed, config=config)
            
            # Clean result
            text = text.strip()
            
            # Validate based on data type
            if data_type == "score":
                # Remove 'x' suffix if present
                text = text.replace('x', '').replace('X', '')
                # Validate format (should be number with optional decimal)
                if not self._is_valid_number(text):
                    return None
                    
            elif data_type == "money":
                # Keep commas for money format
                text = text.replace(' ', '')
                if not self._is_valid_money(text):
                    return None
                    
            elif data_type == "player_count":
                # Should contain '/' separator
                if '/' not in text:
                    return None
            
            return text if text else None
            
        except Exception as e:
            self.logger.error(f"Tesseract error: {e}")
            return None
    
    def _read_with_templates(self, img: np.ndarray, data_type: str) -> Optional[str]:
        """
        Read text using template matching (fast method).
        
        Args:
            img: Input image
            data_type: Type of data
            
        Returns:
            Extracted text or None
        """
        try:
            # Preprocess
            processed = self._preprocess_image(img, data_type)
            
            # Find all digit positions
            digit_positions = []
            
            for digit_name, template in self.digit_templates.items():
                # Multi-scale template matching
                for scale in [0.8, 0.9, 1.0, 1.1, 1.2]:
                    scaled_template = cv2.resize(
                        template, None, 
                        fx=scale, fy=scale,
                        interpolation=cv2.INTER_LINEAR
                    )
                    
                    # Match
                    result = cv2.matchTemplate(
                        processed, scaled_template,
                        cv2.TM_CCOEFF_NORMED
                    )
                    
                    # Find matches above threshold
                    threshold = 0.75
                    locations = np.where(result >= threshold)
                    
                    for pt in zip(*locations[::-1]):
                        digit_value = '.' if digit_name == 'dot' else digit_name
                        digit_positions.append({
                            'x': pt[0],
                            'value': digit_value,
                            'confidence': result[pt[1], pt[0]]
                        })
            
            # Sort by x position
            digit_positions.sort(key=lambda d: d['x'])
            
            # Remove overlapping detections
            filtered_positions = []
            last_x = -100
            
            for pos in digit_positions:
                if pos['x'] - last_x > 10:  # Minimum spacing
                    filtered_positions.append(pos)
                    last_x = pos['x']
            
            # Build result string
            result = ''.join([pos['value'] for pos in filtered_positions])
            
            return result if result else None
            
        except Exception as e:
            self.logger.error(f"Template matching error: {e}")
            return None
    
    def _preprocess_image(self, img: np.ndarray, data_type: str) -> np.ndarray:
        """
        Preprocess image for OCR based on data type.
        
        Args:
            img: Input image
            data_type: Type of data
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # Apply different preprocessing based on data type
        if data_type == "score":
            # Score has good contrast, minimal processing
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
            
        elif data_type == "money":
            # Money might need denoising
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
            
        else:
            # Default processing
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
    
    def _is_valid_number(self, text: str) -> bool:
        """Check if text is valid number format."""
        if not text:
            return False
        try:
            float(text)
            return True
        except:
            return False
    
    def _is_valid_money(self, text: str) -> bool:
        """Check if text is valid money format."""
        if not text:
            return False
        try:
            # Remove commas and check if valid number
            clean = text.replace(',', '')
            float(clean)
            return True
        except:
            return False
    
    def set_method(self, method: OCRMethod):
        """Change OCR method."""
        self.method = method
        if method == OCRMethod.TEMPLATE and not self.template_ready:
            self._load_templates()
        self.logger.info(f"OCR method changed to: {method.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get OCR statistics."""
        avg_time = np.mean(self.read_times) if self.read_times else 0
        
        return {
            'method': self.method.name,
            'avg_read_time_ms': avg_time * 1000,
            'total_reads': len(self.read_times),
            'templates_loaded': len(self.digit_templates),
            'template_ready': self.template_ready
        }