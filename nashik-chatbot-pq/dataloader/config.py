"""
Document Processing Configuration
Uses centralized configuration from app/config/config.py
"""

import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import app config
sys.path.append(str(Path(__file__).parent.parent))

from app.config.config import get_settings

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings from centralized config
settings = get_settings()

# Paths from environment configuration
BASE_DIR = Path(settings.DOCLING_BASE_DIR)
ARTIFACTS_PATH = Path(settings.DOCLING_ARTIFACTS_PATH)
INPUT_ROOT = Path(settings.DOCLING_INPUT_ROOT)
OUTPUT_ROOT = Path(settings.DOCLING_OUTPUT_ROOT)

# Environment Variables for Docling
os.environ["DOCLING_ARTIFACTS_PATH"] = str(ARTIFACTS_PATH)

# Models (with standard HuggingFace naming convention)
VLM_MODEL_FOLDER = ARTIFACTS_PATH / f"ds4sd--{settings.DOCLING_VLM_MODEL}"
LAYOUT_MODEL_FOLDER = ARTIFACTS_PATH / f"docling-project--{settings.DOCLING_LAYOUT_MODEL}"

logger.info(f"Loaded configuration:")
logger.info(f"  BASE_DIR: {BASE_DIR}")
logger.info(f"  ARTIFACTS_PATH: {ARTIFACTS_PATH}")
logger.info(f"  INPUT_ROOT: {INPUT_ROOT}")
logger.info(f"  OUTPUT_ROOT: {OUTPUT_ROOT}")
logger.info(f"  VLM_MODEL_FOLDER: {VLM_MODEL_FOLDER}")
logger.info(f"  LAYOUT_MODEL_FOLDER: {LAYOUT_MODEL_FOLDER}")