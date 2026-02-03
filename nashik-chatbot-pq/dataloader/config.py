import logging
import os
from pathlib import Path

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(r"C:\Users\50014665\Doc_processing")
ARTIFACTS_PATH = BASE_DIR / "docling_models" / "docling_all_models"
INPUT_ROOT = BASE_DIR / "test"
OUTPUT_ROOT = BASE_DIR / "output"

# Environment Variables
os.environ["DOCLING_ARTIFACTS_PATH"] = str(ARTIFACTS_PATH)

# Models
VLM_MODEL_FOLDER = ARTIFACTS_PATH / "ds4sd--SmolDocling-256M-preview"
LAYOUT_MODEL_FOLDER = ARTIFACTS_PATH / "docling-project--docling-layout-heron"