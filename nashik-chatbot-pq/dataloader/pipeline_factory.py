import os
import sys
from pathlib import Path
import tiktoken
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    PictureDescriptionVlmOptions,
    TableStructureOptions,
    RapidOcrOptions,
    AcceleratorOptions,
    AcceleratorDevice
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

# Add parent directory to path to import app config
sys.path.append(str(Path(__file__).parent.parent))

from app.config.config import get_settings
from dataloader.serializer.serializers import CustomSerializerProvider

# Get settings once at module level
settings = get_settings()

# Set up paths — use configured path only if it exists (Docker/Azure).
# On Windows dev machines the container path won't exist; passing None lets
# Docling fall back to its default HuggingFace cache (~/.cache/huggingface).
_configured_path = Path(settings.DOCLING_ARTIFACTS_PATH)
ARTIFACTS_PATH = _configured_path if _configured_path.exists() else None
VLM_MODEL_FOLDER = settings.DOCLING_VLM_MODEL

# Set environment variable for Docling only when path is valid
if ARTIFACTS_PATH is not None:
    os.environ["DOCLING_ARTIFACTS_PATH"] = str(ARTIFACTS_PATH)

# Configuration flags (override via environment variables)
ENABLE_VLM = os.environ.get('ENABLE_VLM', 'false').lower() == 'true'
ENABLE_TABLES = os.environ.get('ENABLE_TABLES', 'true').lower() == 'true'
NUM_THREADS = int(os.environ.get('DOCLING_NUM_THREADS', '8'))  # Use all 8 logical cores by default

# Module-level cache for converter and chunker (singleton pattern)
# Prevents memory leak from recreating Docling models on every processor reload
_converter_instance = None
_chunker_instance = None

def get_pipeline_options():
    # artifacts_path=None tells Docling to use its default HuggingFace cache
    pipeline_options = PdfPipelineOptions(artifacts_path=ARTIFACTS_PATH)

    # 0. Accelerator Settings - Configure FIRST for optimal performance
    # Use AUTO to automatically select best device (CUDA/MPS/CPU)
    # For 8-core VM: use all logical cores for maximum throughput
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=NUM_THREADS,  # Default: 8 (all logical cores)
        device=AcceleratorDevice.AUTO  # Auto-select best device
    )

    # 1. OCR Settings - Handle both text and scanned PDFs
    # Docling automatically skips OCR for text PDFs, runs OCR for scanned PDFs
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions()

    # Use hybrid mode (default): OCR only when needed
    # Set force_full_page_ocr=True only if layout extraction fails
    pipeline_options.ocr_options.force_full_page_ocr = False

    # 2. Table Settings (EXPENSIVE - second most costly after OCR)
    # Can disable via ENABLE_TABLES=false if tables aren't needed
    pipeline_options.do_table_structure = ENABLE_TABLES
    if ENABLE_TABLES:
        pipeline_options.table_structure_options = TableStructureOptions(
            mode=TableFormerMode.FAST,  # FAST mode for better performance
            do_cell_matching=False  # Disable for speed (can enable if needed)
        )

    # 3. VLM / Picture Description Settings
    # PERFORMANCE NOTE: Even with SmolDocling-256M on CPU, transformers library
    # is slow (13-31s per image). Disable for production speed unless critical.
    # Re-enable via ENABLE_VLM=true if picture descriptions are required.
    pipeline_options.do_picture_description = ENABLE_VLM

    if ENABLE_VLM:
        vlm_repo_id = str(VLM_MODEL_FOLDER)
        if vlm_repo_id.startswith("/") or "--" in vlm_repo_id:
            if "SmolDocling" in vlm_repo_id:
                vlm_repo_id = "ds4sd/SmolDocling-256M-preview"

        pipeline_options.picture_description_options = PictureDescriptionVlmOptions(
            repo_id=vlm_repo_id
        )

    # 4. Image Generation Settings
    pipeline_options.images_scale = 2.0
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_table_images = True

    return pipeline_options

def get_converter():
    """
    Get DocumentConverter instance using singleton pattern.
    Creates converter only once to prevent memory leak from reloading ML models.

    CRITICAL: Docling loads ~1-2GB of models (OCR, tables, layout).
    Recreating converter on every processor reload caused 32GB memory leak!
    """
    global _converter_instance

    if _converter_instance is None:
        print("[*] Creating DocumentConverter (loading Docling models ~1-2GB)...")
        _converter_instance = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=get_pipeline_options())
            }
        )
        print("[OK] DocumentConverter created and cached (will be reused)")

    return _converter_instance

def get_chunker():
    """
    Get HybridChunker instance using singleton pattern.
    Reuses tokenizer and chunker to prevent memory overhead.
    """
    global _chunker_instance

    if _chunker_instance is None:
        print("[*] Creating HybridChunker (loading tiktoken encoder)...")
        tokenizer = OpenAITokenizer(
            tokenizer=tiktoken.get_encoding("cl100k_base"),
            max_tokens=8191,
        )
        _chunker_instance = HybridChunker(
            tokenizer=tokenizer,
            serializer_provider=CustomSerializerProvider(),
        )
        print("[OK] HybridChunker created and cached (will be reused)")

    return _chunker_instance
