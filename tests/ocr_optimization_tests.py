# ============================================================================
# OCR OPTIMIZATION TEST VARIANTS
# Target: GTX 1650 (NVIDIA GPU available!)
# ============================================================================

import cv2
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ============================================================================
# VARIANT 1: Tesseract Whitelist (EASIEST - Najvierovatnije najbolji rezultat)
# ============================================================================

class OCR_Variant_1_Whitelist:
    """
    Tesseract sa character whitelist.
    
    Pros:
    - Najjednostavnija implementacija
    - Nema dodatnih dependencies
    - 10-20% brži (očekivano)
    - Možda i tačniji (manje false positives)
    
    Cons:
    - Samo CPU (ne koristi GPU)
    
    Expected: 135ms → 108-122ms
    """
    
    def __init__(self, region):
        self.region = region
        
        # Score može biti: 1.00, 12.34, 123.45, 1234.56
        # Dakle: cifre (0-9), tačka (.), i opciono 'x' na kraju
        self.config = r'--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789.x'
    
    def read_score(self, img):
        """Read score with whitelist."""
        text = pytesseract.image_to_string(img, config=self.config)
        return self.parse_score(text)
    
    def read_money(self, img):
        """Read money with whitelist."""
        # Money može biti: 1234.50, 12,345.67
        # Dakle: cifre, tačka, zarez
        config = r'--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789.,'
        text = pytesseract.image_to_string(img, config=config)
        return self.parse_money(text)
    
    def read_player_count(self, img):
        """Read player count with whitelist."""
        # Player count može biti: 123/1234 ili samo 123
        # Dakle: cifre i /
        config = r'--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789/'
        text = pytesseract.image_to_string(img, config=config)
        return self.parse_player_count(text)
    
    def parse_score(self, text):
        """Parse score from text."""
        # Remove 'x' if present
        text = text.replace('x', '').replace('X', '').strip()
        
        try:
            return float(text)
        except:
            return None
    
    def parse_money(self, text):
        """Parse money from text."""
        # Remove commas, keep decimal point
        text = text.replace(',', '').strip()
        
        try:
            return float(text)
        except:
            return None
    
    def parse_player_count(self, text):
        """Parse player count from text."""
        # Format: "123/1234" → (123, 1234)
        # Or just "123" → 123
        
        if '/' in text:
            parts = text.split('/')
            try:
                left = int(parts[0].strip())
                right = int(parts[1].strip()) if len(parts) > 1 else None
                return (left, right)
            except:
                return None
        else:
            try:
                return int(text.strip())
            except:
                return None


# ============================================================================
# VARIANT 2: PaddleOCR with GPU (FASTEST - Ako radi dobro na GTX 1650)
# ============================================================================

class OCR_Variant_2_PaddleOCR:
    """
    PaddleOCR sa GPU acceleration.
    
    Pros:
    - 50-70% brži (očekivano)
    - Koristi GPU (GTX 1650)
    - Moderna deep learning arhitektura
    
    Cons:
    - Novi dependency (paddlepaddle, paddleocr)
    - Možda manje tačan za ovaj use case
    - Zahteva CUDA setup
    
    Expected: 135ms → 40-60ms (GPU) ili 80-100ms (CPU)
    
    Installation:
        pip install paddlepaddle-gpu paddleocr
        
    Note: Proveri CUDA compatibility sa GTX 1650!
    """
    
    def __init__(self, region):
        self.region = region
        
        # Initialize PaddleOCR
        try:
            from paddleocr import PaddleOCR
            
            self.ocr = PaddleOCR(
                use_textline_orientation=False,
                lang='en',
                use_gpu=True,
                show_log=False
            )
            
            self.gpu_available = True
            
        except Exception as e:
            print(f"PaddleOCR GPU init failed: {e}")
            print("Falling back to CPU mode...")
            
            self.ocr = PaddleOCR(
                use_angle_cls=False,
                lang='en',
                use_gpu=False,  # CPU fallback
                show_log=False,
                det=False,
                rec=True
            )
            
            self.gpu_available = False
    
    def read_score(self, img):
        """Read score with PaddleOCR."""
        # PaddleOCR expects PIL Image or numpy array
        if isinstance(img, np.ndarray):
            # OpenCV image (BGR)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img
        
        # Run OCR
        result = self.ocr.ocr(img_rgb, cls=False)
        
        if result and result[0]:
            # Extract text from result
            # Format: [[[bbox], (text, confidence)]]
            text = result[0][0][1][0] if result[0][0] else ""
            return self.parse_score(text)
        
        return None
    
    def parse_score(self, text):
        """Parse score from text."""
        text = text.replace('x', '').replace('X', '').strip()
        
        try:
            return float(text)
        except:
            return None


# ============================================================================
# VARIANT 3: EasyOCR with GPU (ALTERNATIVE - Možda bolji od PaddleOCR)
# ============================================================================

class OCR_Variant_3_EasyOCR:
    """
    EasyOCR sa GPU acceleration.
    
    Pros:
    - Slično PaddleOCR po brzini
    - Možda tačniji za engleski text
    - Dobar GPU support (GTX 1650)
    
    Cons:
    - Novi dependency
    - Sporija inicijalizacija
    
    Expected: 135ms → 50-70ms (GPU) ili 90-110ms (CPU)
    
    Installation:
        pip install easyocr
    """
    
    def __init__(self, region):
        self.region = region
        
        try:
            import easyocr
            
            # Initialize EasyOCR
            self.reader = easyocr.Reader(
                ['en'],
                gpu=True,  # GTX 1650
                verbose=False
            )
            
            self.gpu_available = True
            
        except Exception as e:
            print(f"EasyOCR GPU init failed: {e}")
            
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self.gpu_available = False
    
    def read_score(self, img):
        """Read score with EasyOCR."""
        # EasyOCR expects numpy array or PIL Image
        if not isinstance(img, np.ndarray):
            img = np.array(img)
        
        # Run OCR
        results = self.reader.readtext(
            img,
            detail=0,  # Don't return bounding boxes (faster)
            paragraph=False  # Don't group text (faster)
        )
        
        if results:
            text = results[0]
            return self.parse_score(text)
        
        return None
    
    def parse_score(self, text):
        """Parse score from text."""
        text = text.replace('x', '').replace('X', '').strip()
        
        try:
            return float(text)
        except:
            return None


# ============================================================================
# VARIANT 4: Tesseract + Improved Preprocessing
# ============================================================================

class OCR_Variant_4_Preprocessing:
    """
    Tesseract sa poboljšanim preprocessing-om.
    
    Pros:
    - Može poboljšati accuracy
    - Nema novih dependencies
    
    Cons:
    - Preprocessing dodaje vreme (~10-20ms)
    - Možda nema speedup
    
    Expected: 135ms → 145-155ms (sporije, ali tačnije!)
    """
    
    def __init__(self, region):
        self.region = region
        self.config = r'--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789.x'
    
    def preprocess_image(self, img):
        """
        Advanced preprocessing for better OCR accuracy.
        
        Steps:
        1. Grayscale
        2. Denoise
        3. Adaptive threshold
        4. Morphology (remove small artifacts)
        5. Optional: Resize if too small
        """
        # Grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Denoise (removes noise/artifacts)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Adaptive threshold (better than fixed)
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # Block size
            2    # C constant
        )
        
        # Morphology - remove small dots
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Optional: Resize if image is small
        h, w = cleaned.shape
        if h < 40:
            # Upscale to at least 40px height
            scale = 40 / h
            new_w = int(w * scale)
            new_h = int(h * scale)
            cleaned = cv2.resize(cleaned, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        
        return cleaned
    
    def read_score(self, img):
        """Read score with advanced preprocessing."""
        # Preprocess
        processed = self.preprocess_image(img)
        
        # OCR
        text = pytesseract.image_to_string(processed, config=self.config)
        return self.parse_score(text)
    
    def parse_score(self, text):
        """Parse score from text."""
        text = text.replace('x', '').replace('X', '').strip()
        
        try:
            return float(text)
        except:
            return None


# ============================================================================
# BENCHMARK SCRIPT - Test sve varijante
# ============================================================================

def benchmark_all_variants():
    """
    Benchmark sve OCR varijante.
    
    Usage:
        python ocr_benchmark.py
    """
    import time
    import mss
    
    # Test region (podesi na svoje koordinate)
    test_region = {
        'left': 448+3840,
        'top': 399,
        'width': 380,
        'height': 130
    }
    
    # Initialize sve varijante
    variants = {
        'V1: Whitelist': OCR_Variant_1_Whitelist(test_region),
        'V2: PaddleOCR': None,  # Inicijalizuj ako imaš instaliran
        'V3: EasyOCR': None,    # Inicijalizuj ako imaš instaliran
        'V4: Preprocessing': OCR_Variant_4_Preprocessing(test_region),
    }
    
    # Initialize Paddle i Easy ako dostupni
    try:
        variants['V2: PaddleOCR'] = OCR_Variant_2_PaddleOCR(test_region)
        print("✅ PaddleOCR initialized")
    except:
        print("❌ PaddleOCR not available")
    
    try:
        variants['V3: EasyOCR'] = OCR_Variant_3_EasyOCR(test_region)
        print("✅ EasyOCR initialized")
    except:
        print("❌ EasyOCR not available")
    
    # Capture test image
    with mss.mss() as sct:
        screenshot = sct.grab(test_region)
        test_img = np.array(screenshot)[:, :, :3]  # Remove alpha
    
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    
    for name, variant in variants.items():
        if variant is None:
            continue
        
        # Warmup
        for _ in range(5):
            variant.read_score(test_img)
        
        # Benchmark
        times = []
        for _ in range(100):
            start = time.perf_counter()
            result = variant.read_score(test_img)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = np.mean(times)
        min_time = np.min(times)
        max_time = np.max(times)
        
        print(f"\n{name}:")
        print(f"  Avg: {avg_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"  Result: {result}")
    
    print("\n" + "="*60)


# ============================================================================
# PREPORUKA ZA TESTIRANJE
# ============================================================================

"""
TESTING PLAN:

1. TEST Variant 1 (Whitelist) - START HERE!
   - Najjednostavnije
   - Samo promeni config string
   - Očekivano: 108-122ms (10-20% brže)
   - Benchmark: python utils/ocr_speed_benchmark.py
   
2. IF Variant 1 good → DONE! (možda je dovoljno)

3. IF want more speed → TEST Variant 2 (PaddleOCR)
   Installation:
   ```
   # For GTX 1650 (Turing, CUDA 10.1+)
   pip install paddlepaddle-gpu
   pip install paddleocr
   ```
   
   Očekivano: 40-60ms (50-70% brže!)
   
4. IF PaddleOCR problemi → TEST Variant 3 (EasyOCR)
   Installation:
   ```
   pip install easyocr
   ```
   
   Očekivano: 50-70ms (45-65% brže)

5. IF accuracy problems → TEST Variant 4 (Preprocessing)
   Očekivano: Sporije ali tačnije

RECOMMENDATION:
Start with Variant 1 (whitelist).
If need more speed AND have time → try PaddleOCR (V2).
"""

if __name__ == "__main__":
    #import paddle
    

    #print(paddle.device.get_device())
    #print(paddle.is_compiled_with_cuda())
    #print('******* >>> ',paddle.device.get_device())   # Trebalo bi da vidiš npr. 'gpu:0'


    
    benchmark_all_variants()
