import os
import sys
from pathlib import Path
import tiktoken
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
    PictureDescriptionVlmOptions,
    TableStructureOptions
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

# Set up paths
ARTIFACTS_PATH = Path(settings.DOCLING_ARTIFACTS_PATH)
VLM_MODEL_FOLDER = ARTIFACTS_PATH / f"ds4sd--{settings.DOCLING_VLM_MODEL}"

# Set environment variable for Docling
os.environ["DOCLING_ARTIFACTS_PATH"] = str(ARTIFACTS_PATH)

def get_pipeline_options():
    pipeline_options = PdfPipelineOptions(artifacts_path=ARTIFACTS_PATH)

    # 1. Table Settings
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options = TableStructureOptions(
        mode=TableFormerMode.ACCURATE,
        do_cell_matching=False
    )

    # 2. VLM / Picture Description Settings
    pipeline_options.do_picture_description = True
    pipeline_options.picture_description_options = PictureDescriptionVlmOptions(
        repo_id=str(VLM_MODEL_FOLDER)
    )
    
    # 3. Image Generation Settings
    # Optimized for memory efficiency
    pipeline_options.images_scale = 1.0  # Reduced from 2.0 to save memory
    pipeline_options.generate_page_images = False # Disable full page images to save memory
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_table_images = True
    
    # 4. Threading
    # Limit threads to prevent memory explosion on multi-core systems
    # Using 4 threads is a safe default for most containers
    pipeline_options.accelerator_options.num_threads = 4
    
    return pipeline_options

def get_converter():
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=get_pipeline_options())
        }
    )

def get_chunker():
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.get_encoding("cl100k_base"),
        max_tokens=8191,
    )
    return HybridChunker(
        tokenizer=tokenizer,
        serializer_provider=CustomSerializerProvider(),
    )