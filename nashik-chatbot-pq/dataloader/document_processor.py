import sys
import time
import json
import logging
from pathlib import Path
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

# Add parent directory to path to import app config
sys.path.append(str(Path(__file__).parent.parent))

from app.config.config import get_settings
import pipeline_factory

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Set up paths
ARTIFACTS_PATH = Path(settings.DOCLING_ARTIFACTS_PATH)
INPUT_ROOT = Path(settings.DOCLING_INPUT_ROOT)
OUTPUT_ROOT = Path(settings.DOCLING_OUTPUT_ROOT)
VLM_MODEL_FOLDER = ARTIFACTS_PATH / f"ds4sd--{settings.DOCLING_VLM_MODEL}"
LAYOUT_MODEL_FOLDER = ARTIFACTS_PATH / f"docling-project--{settings.DOCLING_LAYOUT_MODEL}"

def process_files():
    # Verify paths
    if not VLM_MODEL_FOLDER.exists():
        logger.error(f"VLM Model folder not found at: {VLM_MODEL_FOLDER}")
    else:
        logger.info(f"Confirmed local VLM model at: {VLM_MODEL_FOLDER}")

    if not LAYOUT_MODEL_FOLDER.exists():
        logger.warning(f"Layout Model folder not found at: {LAYOUT_MODEL_FOLDER}")

    pdf_files = list(INPUT_ROOT.rglob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {INPUT_ROOT}")
        return

    # Initialize components
    doc_converter = pipeline_factory.get_converter()
    chunker = pipeline_factory.get_chunker()

    print(f"Found {len(pdf_files)} PDF files. Starting conversion...")

    for pdf_file in pdf_files:
        try:
            start_time = time.time()
            print(f"\n--- Processing: {pdf_file.name} ---")
            
            # Convert
            conv_res = doc_converter.convert(pdf_file)
            
            # Output Directory
            relative_path = pdf_file.relative_to(INPUT_ROOT)
            doc_output_dir = OUTPUT_ROOT / relative_path.parent / pdf_file.stem
            doc_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Subdirectories
            tables_dir = doc_output_dir / "tables"
            figures_dir = doc_output_dir / "figures"
            tables_dir.mkdir(exist_ok=True)
            figures_dir.mkdir(exist_ok=True)
            
            doc_filename = pdf_file.stem

            # 1. Save Page Images
            for page_no, page in conv_res.document.pages.items():
                page_image_filename = doc_output_dir / f"{doc_filename}-page-{page.page_no}.png"
                with page_image_filename.open("wb") as fp:
                    page.image.pil_image.save(fp, format="PNG")
            
            # 2. Save Element Images
            table_counter = 0
            picture_counter = 0
            for element, _level in conv_res.document.iterate_items():
                if isinstance(element, TableItem):
                    table_counter += 1
                    if element.image:
                        element_image_filename = tables_dir / f"{doc_filename}-table-{table_counter}.png"
                        with element_image_filename.open("wb") as fp:
                            element.get_image(conv_res.document).save(fp, "PNG")

                if isinstance(element, PictureItem):
                    picture_counter += 1
                    if element.image:
                        element_image_filename = figures_dir / f"{doc_filename}-picture-{picture_counter}.png"
                        with element_image_filename.open("wb") as fp:
                            element.get_image(conv_res.document).save(fp, "PNG")

            # 3. Save Full Document Exports
            md_embedded = doc_output_dir / f"{doc_filename}-embedded.md"
            conv_res.document.save_as_markdown(md_embedded, image_mode=ImageRefMode.EMBEDDED)

            docling_json_file = doc_output_dir / f"{doc_filename}_docling.json"
            conv_res.document.save_as_json(docling_json_file)
            print(f"Saved Docling JSON to {docling_json_file}")
            
            # 4. Chunking & Serialization
            print(f"Chunking document...")
            chunk_iter = chunker.chunk(dl_doc=conv_res.document)
            chunks = list(chunk_iter)
            
            serialized_chunks = []
            for i, chunk in enumerate(chunks):
                chunk_text = chunker.contextualize(chunk=chunk)
                serialized_chunks.append({
                    "chunk_id": i,
                    "text": chunk_text,
                    "metadata": chunk.meta.export_json_dict()
                })
            
            chunks_file = doc_output_dir / f"{doc_filename}-chunks.json"
            with open(chunks_file, "w", encoding="utf-8") as f:
                json.dump(serialized_chunks, f, ensure_ascii=False, indent=2)
            
            print(f"Saved {len(chunks)} chunks to {chunks_file}")

            end_time = time.time() - start_time
            print(f"Finished {pdf_file.name} in {end_time:.2f}s. Saved to: {doc_output_dir}")
            
        except Exception as e:
            print(f"Error converting {pdf_file.name}: {e}")
            import traceback
            traceback.print_exc()

    print("\nAll processing complete.")

if __name__ == "__main__":
    process_files()
