import os
import sys
from pathlib import Path
import tiktoken
from docling.datamodel.base_models import InputFormat
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
NUM_THREADS = int(os.environ.get('DOCLING_NUM_THREADS', '8'))
# Set DOCLING_SIMPLE_PIPELINE=true on local dev machines where HuggingFace
# model downloads are blocked. On deployed servers (where models are cached)
# leave unset to use the full StandardPipeline for best extraction quality.
USE_SIMPLE_PIPELINE = os.environ.get('DOCLING_SIMPLE_PIPELINE', 'false').lower() == 'true'

# Module-level cache for converter and chunker (singleton pattern)
# Prevents memory leak from recreating Docling models on every processor reload
_converter_instance = None
_chunker_instance = None


def _get_standard_pipeline_options():
    """Full pipeline with HuggingFace layout model — use on deployed servers."""
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions, TableFormerMode, PictureDescriptionVlmOptions,
        TableStructureOptions, AcceleratorOptions, AcceleratorDevice
    )
    opts = PdfPipelineOptions(artifacts_path=ARTIFACTS_PATH)
    opts.accelerator_options = AcceleratorOptions(
        num_threads=NUM_THREADS, device=AcceleratorDevice.AUTO
    )
    opts.do_ocr = False
    opts.do_table_structure = ENABLE_TABLES
    if ENABLE_TABLES:
        opts.table_structure_options = TableStructureOptions(
            mode=TableFormerMode.FAST, do_cell_matching=False
        )
    opts.do_picture_description = ENABLE_VLM
    if ENABLE_VLM:
        vlm_repo_id = str(VLM_MODEL_FOLDER)
        if vlm_repo_id.startswith("/") or "--" in vlm_repo_id:
            if "SmolDocling" in vlm_repo_id:
                vlm_repo_id = "ds4sd/SmolDocling-256M-preview"
        opts.picture_description_options = PictureDescriptionVlmOptions(repo_id=vlm_repo_id)
    opts.generate_page_images = False
    opts.generate_picture_images = True
    opts.generate_table_images = True
    return opts


def _get_simple_pipeline_options():
    """
    Simple pipeline — no HuggingFace model downloads.
    Uses docling_parse only. For local dev where XetHub CDN is blocked.
    """
    try:
        from docling.datamodel.pipeline_options import SimplePdfPipelineOptions
        print("[*] Using SimplePdfPipelineOptions (no model downloads)")
        return SimplePdfPipelineOptions()
    except ImportError:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        opts = PdfPipelineOptions(artifacts_path=ARTIFACTS_PATH)
        opts.do_ocr = False
        opts.do_table_structure = False
        opts.do_picture_description = False
        opts.generate_page_images = False
        opts.generate_picture_images = False
        opts.generate_table_images = False
        print("[*] SimplePdfPipelineOptions unavailable — using minimal PdfPipelineOptions")
        return opts


def get_converter():
    """
    Get DocumentConverter instance using singleton pattern.

    DOCLING_SIMPLE_PIPELINE=true  → local dev, no HuggingFace downloads
    DOCLING_SIMPLE_PIPELINE=false → deployed server, full quality pipeline
    """
    global _converter_instance

    if _converter_instance is None:
        if USE_SIMPLE_PIPELINE:
            print("[*] Creating DocumentConverter (simple pipeline — no model downloads)...")
            pipeline_options = _get_simple_pipeline_options()
        else:
            print("[*] Creating DocumentConverter (standard pipeline — HuggingFace models)...")
            pipeline_options = _get_standard_pipeline_options()

        _converter_instance = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
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
