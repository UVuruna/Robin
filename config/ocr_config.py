"""
OCR Configuration per Reader Type
Optimized for single-word recognition
"""

# ============================================================
# TESSERACT CONFIGS - Per Reader Type
# ============================================================

OCR_CONFIGS = {
    "score": {
        # Čita: "1.52x", "12.34x", "100.00x"
        "whitelist": "0123456789.",
        "psm": 7,  # Single line
        "oem": 3,  # Default OCR Engine Mode
        "custom_config": "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789."
    },
    
    "money": {
        # Čita: "1,234.56", "12,345.78", "123,456.78"
        "whitelist": "0123456789.",
        "psm": 7,  # Single line
        "oem": 3,
        "custom_config": "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789."
    },
    
    "player_count": {
        # Čita: "123/1234", "45/2134"
        "whitelist": "0123456789/",
        "psm": 7,  # Single line
        "oem": 3,
        "custom_config": "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/"
    }
}


# ============================================================
# PADDLEOCR CONFIGS - Per Reader Type (DISABLED - Future Use)
# ============================================================
# NOTE: PaddleOCR currently not working with Python 3.13
# Will be enabled later when compatible

PADDLE_CONFIGS = None  # Disabled for now


# ============================================================
# POST-PROCESSING - Character Validation
# ============================================================

ALLOWED_CHARS = {
    "score": set("0123456789.,x"),
    "money": set("0123456789.,"),
    "player_count": set("0123456789/")
}


def get_tesseract_config(reader_type: str) -> str:
    """Get Tesseract config string for reader type"""
    if reader_type not in OCR_CONFIGS:
        raise ValueError(f"Unknown reader type: {reader_type}")
    return OCR_CONFIGS[reader_type]["custom_config"]


def get_paddle_config(reader_type: str) -> dict:
    """Get PaddleOCR config dict for reader type"""
    if reader_type not in PADDLE_CONFIGS:
        raise ValueError(f"Unknown reader type: {reader_type}")
    return PADDLE_CONFIGS[reader_type].copy()


def validate_ocr_result(text: str, reader_type: str) -> str:
    """
    Validate and clean OCR result based on allowed characters
    
    Args:
        text: Raw OCR result
        reader_type: Type of reader (score/money/player_count)
    
    Returns:
        Cleaned text with only allowed characters
    """
    if reader_type not in ALLOWED_CHARS:
        return text
    
    allowed = ALLOWED_CHARS[reader_type]
    cleaned = ''.join(c for c in text if c in allowed)
    return cleaned


# ============================================================
# GPU MEMORY ALLOCATION - For 6 Parallel Processes (DISABLED)
# ============================================================
# NOTE: GPU acceleration disabled - Tesseract whitelist is sufficient
# GTX 1650 4GB VRAM not needed for current OCR performance

GPU_CONFIG = None  # Not used currently


# ============================================================
# BENCHMARK - Expected Performance
# ============================================================

EXPECTED_PERFORMANCE = {
    "tesseract_default": {
        "score": 135,      # ms
        "money": 121,      # ms
        "player_count": 117  # ms
    },
    
    "tesseract_whitelist": {
        "score": 110,      # ms (18% faster)
        "money": 98,       # ms (19% faster)
        "player_count": 95   # ms (19% faster)
    },
    
    "paddleocr_gpu": {
        "score": 40,       # ms (70% faster than default!)
        "money": 36,       # ms
        "player_count": 35   # ms
    }
}


# ============================================================
# MULTIPROCESSING SAFETY
# ============================================================

MULTIPROCESSING_CONFIG = {
    "use_spawn": True,  # Use 'spawn' for Windows compatibility
    "max_workers": 6,  # 6 bookmakers in parallel
}