# core/fast_cnn_ocr.py
# CNN OCR Engine za brzo prepoznavanje cifara
# 
# Koristi trenirani model iz data/digit_cnn.pth
# Cilj: 2-5ms inference time

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import cv2
import time
import os
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class Detection:
    """Single digit detection"""
    digit: int
    confidence: float
    position: Tuple[int, int]


# ============================================================================
# CNN ARCHITECTURE (must match training!)
# ============================================================================

class DigitCNN(nn.Module):
    """CNN za cifre 0-9 (kopija iz train_cnn.py)"""
    
    def __init__(self):
        super(DigitCNN, self).__init__()
        
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.3)
        
        self.fc1 = nn.Linear(64 * 3 * 3, 128)
        self.fc2 = nn.Linear(128, 10)
        
    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.pool(F.relu(self.conv3(x)))
        
        x = x.view(-1, 64 * 3 * 3)
        
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        
        return x


# ============================================================================
# FAST CNN OCR ENGINE
# ============================================================================

class FastCNNOCR:
    """
    Brz CNN-based OCR za jednocifrene/višecifrene brojeve.
    
    Optimizacije:
    - Batched inference (obradi više windows odjednom)
    - ROI detection (smanji prostor pretraživanja)
    - Sliding window sa velikim stride-om
    - Non-maximum suppression
    
    Target: 2-5ms za tipičan Aviator score (3-4 cifre)
    """
    
    def __init__(self, model_path: str = "data/models/digit_cnn.pth"):
        """
        Args:
            model_path: Path to trained model
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load model
        self.model = DigitCNN().to(self.device)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"CNN model not found: {model_path}\n"
                f"Run: python train_cnn.py"
            )
        
        self.model.load_state_dict(
            torch.load(model_path, map_location=self.device)
        )
        self.model.eval()
        
        # Config
        self.window_size = (28, 28)
        self.stride = 6  # Veliki stride za brzinu
        self.min_confidence = 0.80
        self.nms_iou_threshold = 0.3
        
        # Warmup
        self._warmup()
        
    def _warmup(self):
        """Warmup GPU/CPU"""
        dummy = torch.randn(1, 1, 28, 28).to(self.device)
        with torch.no_grad():
            self.model(dummy)
    
    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Preprocess image for CNN.
        
        Args:
            img: BGR ili grayscale image
            
        Returns:
            Binary image
        """
        # Grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Check if invert needed
        if np.mean(gray) < 127:
            gray = cv2.bitwise_not(gray)
        
        # Enhance contrast
        gray = cv2.equalizeHist(gray)
        
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,  # White digits on black
            11, 2
        )
        
        # Denoise
        binary = cv2.medianBlur(binary, 3)
        
        return binary
    
    def _detect_roi(self, binary: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect region of interest (text area).
        
        Returns:
            (x, y, w, h) or None
        """
        # Vertical projection
        vert_proj = np.sum(binary, axis=1)
        threshold = np.max(vert_proj) * 0.2
        text_rows = np.where(vert_proj > threshold)[0]
        
        if len(text_rows) == 0:
            return None
        
        y_min = text_rows[0]
        y_max = text_rows[-1]
        
        # Horizontal projection
        horiz_proj = np.sum(binary[y_min:y_max, :], axis=0)
        threshold = np.max(horiz_proj) * 0.1
        text_cols = np.where(horiz_proj > threshold)[0]
        
        if len(text_cols) == 0:
            return None
        
        x_min = text_cols[0]
        x_max = text_cols[-1]
        
        # Add padding
        padding = 5
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(binary.shape[1], x_max + padding)
        y_max = min(binary.shape[0], y_max + padding)
        
        return (x_min, y_min, x_max - x_min, y_max - y_min)
    
    def _extract_windows(self, img: np.ndarray) -> List[Tuple[np.ndarray, Tuple[int, int]]]:
        """
        Extract sliding windows.
        
        Returns:
            List of (window_img, (x, y))
        """
        h, w = img.shape
        win_h, win_w = self.window_size
        
        windows = []
        
        for y in range(0, max(1, h - win_h + 1), self.stride):
            for x in range(0, max(1, w - win_w + 1), self.stride):
                # Make sure we don't go out of bounds
                if y + win_h <= h and x + win_w <= w:
                    window = img[y:y+win_h, x:x+win_w]
                    windows.append((window, (x, y)))
        
        return windows
    
    def _predict_batch(self, windows: List[np.ndarray]) -> np.ndarray:
        """
        Batch prediction za sve windows.
        
        Args:
            windows: List of 28x28 images
            
        Returns:
            Array of probabilities (N x 10)
        """
        # Prepare batch
        batch = []
        for window in windows:
            # Normalize
            window = window.astype(np.float32) / 255.0
            # Add channel dim
            window = window[np.newaxis, :, :]
            batch.append(window)
        
        # Stack into tensor
        batch_tensor = torch.from_numpy(np.array(batch)).to(self.device)
        
        # Inference
        with torch.no_grad():
            outputs = self.model(batch_tensor)
            probs = F.softmax(outputs, dim=1)
        
        return probs.cpu().numpy()
    
    def _nms(self, detections: List[Detection]) -> List[Detection]:
        """Non-maximum suppression"""
        if len(detections) <= 1:
            return detections
        
        # Sort by confidence
        detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
        
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            
            # Remove overlapping
            detections = [
                d for d in detections
                if abs(d.position[0] - best.position[0]) > 10  # At least 10px apart
            ]
        
        # Sort by x position
        keep.sort(key=lambda d: d.position[0])
        
        return keep
    
    def recognize(self, img: np.ndarray, debug: bool = False) -> str:
        """
        Main recognition function.
        
        Args:
            img: Input image (BGR or grayscale)
            debug: Enable debug output
            
        Returns:
            Recognized number as string (e.g., "5.71")
        """
        start = time.perf_counter()
        
        # Preprocess
        binary = self._preprocess(img)
        
        # Detect ROI
        roi = self._detect_roi(binary)
        if roi:
            x, y, w, h = roi
            binary = binary[y:y+h, x:x+w]
            
            if debug:
                print(f"ROI: {roi}")
        
        # Extract windows
        windows_data = self._extract_windows(binary)
        
        if len(windows_data) == 0:
            return ""
        
        windows, positions = zip(*windows_data)
        
        # Batch predict
        probs = self._predict_batch(windows)
        
        # Extract detections
        detections = []
        for i, (prob, pos) in enumerate(zip(probs, positions)):
            digit = np.argmax(prob)
            confidence = prob[digit]
            
            if confidence >= self.min_confidence:
                detections.append(Detection(
                    digit=int(digit),
                    confidence=float(confidence),
                    position=pos
                ))
        
        # NMS
        detections = self._nms(detections)
        
        # Build result
        result = "".join(str(d.digit) for d in detections)
        
        # Post-process: add decimal point for Aviator scores
        if len(result) >= 2 and '.' not in result:
            # Aviator format: X.XX
            if len(result) >= 3:
                result = result[:-2] + '.' + result[-2:]
        
        elapsed = (time.perf_counter() - start) * 1000
        
        if debug:
            print(f"⚡ CNN Time: {elapsed:.2f}ms")
            print(f"📊 Detections: {len(detections)}")
            for d in detections:
                print(f"   {d.digit} @ {d.position} (conf: {d.confidence:.3f})")
            print(f"✅ Result: '{result}'")
        
        return result


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("FAST CNN OCR - TEST")
    print("=" * 70)
    
    try:
        ocr = FastCNNOCR()
        print("✅ Model loaded successfully")
        
        # Test sa slikom ako postoji
        test_img = "test_571.png"
        
        if os.path.exists(test_img):
            print(f"\n{'='*70}")
            print(f"Testing: {test_img}")
            print(f"{'='*70}")
            
            img = cv2.imread(test_img)
            
            # Warmup
            for _ in range(10):
                ocr.recognize(img)
            
            # Benchmark
            times = []
            results = []
            
            for i in range(100):
                start = time.perf_counter()
                result = ocr.recognize(img, debug=(i == 0))
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)
                results.append(result)
            
            print(f"\n{'='*70}")
            print("BENCHMARK (100 runs):")
            print(f"{'='*70}")
            print(f"Average: {np.mean(times):.2f}ms")
            print(f"Median:  {np.median(times):.2f}ms")
            print(f"Min:     {np.min(times):.2f}ms")
            print(f"Max:     {np.max(times):.2f}ms")
            print(f"Most common result: {max(set(results), key=results.count)}")
            print(f"{'='*70}")
        
        else:
            print(f"\n⚠️  Test image not found: {test_img}")
            print("   Place a test image and run again")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()