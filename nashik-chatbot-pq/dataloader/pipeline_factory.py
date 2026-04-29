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

# Module-level cache for converter and chunker (singleton pattern)
# Prevents memory leak from recreating Docling models on every processor reload
_converter_instance = None
_chunker_instance = None


def _try_simple_pipeline_options():
    """
    Try to build SimplePdfPipelineOptions (no ML model downloads).
    Falls back to standard PdfPipelineOptions with all heavy features disabled
    if SimplePdfPipelineOptions is not available in the installed docling version.
    """
    try:
        from docling.datamodel.pipeline_options import SimplePdfPipelineOptions
        opts = SimplePdfPipelineOptions()
        print("[*] Using SimplePdfPipelineOptions (no model downloads)")
        return opts, True
    except ImportError:
        pass

    # Fallback: standard options with everything that causes downloads disabled
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    opts = PdfPipelineOptions(artifacts_path=ARTIFACTS_PATH)
    opts.do_ocr = False
    opts.do_table_structure = False
    opts.do_picture_description = False
    opts.generate_page_images = False
    opts.generate_picture_images = False
    opts.generate_table_images = False
    print("[*] SimplePdfPipelineOptions not available — using minimal PdfPipelineOptions")
    return opts, False


def get_converter():
    """
    Get DocumentConverter instance using singleton pattern.
    Uses SimplePdfPipelineOptions to avoid downloading HuggingFace layout models,
    which fail on corporate networks that block the XetHub CDN.
    """
    global _converter_instance

    if _converter_instance is None:
        print("[*] Creating DocumentConverter (simple pipeline — no model downloads)...")
        pipeline_options, is_simple = _try_simple_pipeline_options()
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
