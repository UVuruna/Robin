# core/capture/screen_capture.py
# VERSION: 1.0 - COMPLETE
# PURPOSE: Brzo hvatanje screenshot-ova sa MSS

import mss
import numpy as np
import cv2
import logging
from typing import Optional, Tuple, Dict, Any
import time

class ScreenCapture:
    """
    Optimizovan screen capture sa MSS bibliotekom.
    10x brži od pyautogui.screenshot().
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sct = mss.mss()
        
        # Cache monitor info
        self.monitors = self.sct.monitors
        self.primary_monitor = self.monitors[1]  # Index 0 je combined, 1 je primary
        
        # Performance tracking
        self.capture_times = []
        
        self.logger.info(f"Initialized with {len(self.monitors)-1} monitor(s)")
        
    def capture_region(self, coords: Dict[str, int]) -> Optional[np.ndarray]:
        """
        Capture specific screen region.
        
        Args:
            coords: Dict with 'left', 'top', 'width', 'height'
            
        Returns:
            numpy array (BGR format) or None if error
        """
        try:
            start_time = time.perf_counter()
            
            # MSS format
            monitor = {
                "left": coords.get("left", 0),
                "top": coords.get("top", 0),
                "width": coords.get("width", 100),
                "height": coords.get("height", 50)
            }
            
            # Capture
            screenshot = self.sct.grab(monitor)
            
            # Convert to numpy array (BGRA -> BGR)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Track performance
            capture_time = time.perf_counter() - start_time
            self.capture_times.append(capture_time)
            if len(self.capture_times) > 100:
                self.capture_times.pop(0)
            
            return img
            
        except Exception as e:
            self.logger.error(f"Failed to capture region: {e}")
            return None
    
    def capture_full_screen(self, monitor_idx: int = 1) -> Optional[np.ndarray]:
        """
        Capture full screen.
        
        Args:
            monitor_idx: Monitor index (1 for primary, 2 for secondary, etc.)
            
        Returns:
            numpy array or None
        """
        try:
            if monitor_idx >= len(self.monitors):
                self.logger.warning(f"Monitor {monitor_idx} not found")
                return None
            
            screenshot = self.sct.grab(self.monitors[monitor_idx])
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            return img
            
        except Exception as e:
            self.logger.error(f"Failed to capture full screen: {e}")
            return None
    
    def save_screenshot(self, img: np.ndarray, filepath: str) -> bool:
        """
        Save screenshot to file.
        
        Args:
            img: Image array
            filepath: Path to save
            
        Returns:
            True if successful
        """
        try:
            cv2.imwrite(filepath, img)
            self.logger.debug(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")
            return False
    
    def preprocess_for_ocr(self, img: np.ndarray, 
                          grayscale: bool = True,
                          invert: bool = False,
                          threshold: bool = True) -> np.ndarray:
        """
        Preprocess image for OCR.
        
        Args:
            img: Input image
            grayscale: Convert to grayscale
            invert: Invert colors
            threshold: Apply Otsu thresholding
            
        Returns:
            Preprocessed image
        """
        processed = img.copy()
        
        # Grayscale
        if grayscale and len(processed.shape) == 3:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
        
        # Invert
        if invert:
            processed = cv2.bitwise_not(processed)
        
        # Threshold
        if threshold:
            _, processed = cv2.threshold(
                processed, 0, 255, 
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        
        return processed
    
    def find_template(self, img: np.ndarray, template: np.ndarray,
                     threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        """
        Find template in image using template matching.
        
        Args:
            img: Source image
            template: Template to find
            threshold: Match threshold (0-1)
            
        Returns:
            (x, y) coordinates or None
        """
        try:
            # Convert to grayscale if needed
            if len(img.shape) == 3:
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                img_gray = img
                
            if len(template.shape) == 3:
                template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = template
            
            # Template matching
            result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            
            # Find best match
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                return max_loc
            
            return None
            
        except Exception as e:
            self.logger.error(f"Template matching failed: {e}")
            return None
    
    def get_pixel_color(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """
        Get color of specific pixel.
        
        Args:
            x, y: Pixel coordinates
            
        Returns:
            (R, G, B) tuple or None
        """
        try:
            monitor = {
                "left": x,
                "top": y,
                "width": 1,
                "height": 1
            }
            
            screenshot = self.sct.grab(monitor)
            img = np.array(screenshot)
            
            # Return RGB (MSS returns BGRA)
            return (img[0, 0, 2], img[0, 0, 1], img[0, 0, 0])
            
        except Exception as e:
            self.logger.error(f"Failed to get pixel color: {e}")
            return None
    
    def get_average_color(self, coords: Dict[str, int]) -> Optional[Tuple[float, float, float]]:
        """
        Get average color of region.
        
        Args:
            coords: Region coordinates
            
        Returns:
            (R, G, B) averages or None
        """
        img = self.capture_region(coords)
        if img is None:
            return None
        
        try:
            # Calculate mean for each channel
            b, g, r = cv2.split(img)
            return (float(np.mean(r)), float(np.mean(g)), float(np.mean(b)))
            
        except Exception as e:
            self.logger.error(f"Failed to calculate average color: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get capture statistics."""
        if not self.capture_times:
            return {
                'avg_capture_time_ms': 0,
                'min_capture_time_ms': 0,
                'max_capture_time_ms': 0,
                'total_captures': 0
            }
        
        return {
            'avg_capture_time_ms': np.mean(self.capture_times) * 1000,
            'min_capture_time_ms': min(self.capture_times) * 1000,
            'max_capture_time_ms': max(self.capture_times) * 1000,
            'total_captures': len(self.capture_times)
        }
    
    def cleanup(self):
        """Cleanup resources."""
        try:
            self.sct.close()
        except:
            pass