"""
CLI entry point for document embedding processor
Supports batch processing to prevent OOM issues
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dataloader.document_embedding_processor import DocumentEmbeddingProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """
    Main entry point for document embedding processor
    Supports BATCH_SIZE environment variable to limit documents per run
    """
    # Get batch size from environment variable (default: None = process all)
    batch_size_str = os.environ.get('BATCH_SIZE')
    batch_size = None

    if batch_size_str:
        try:
            batch_size = int(batch_size_str)
            logger.info(f"Batch size limit: {batch_size} documents per run")
        except ValueError:
            logger.warning(f"Invalid BATCH_SIZE '{batch_size_str}', processing all documents")

    # Initialize and run processor
    processor = DocumentEmbeddingProcessor()

    try:
        logger.info("Starting document embedding processor...")
        stats = processor.run(batch_size=batch_size)

        logger.info("\n" + "=" * 80)
        logger.info("Processing Complete!")
        logger.info("=" * 80)
        logger.info(f"Documents processed: {stats['documents_processed']}")
        logger.info(f"Documents completed: {stats['documents_completed']}")
        logger.info(f"Documents failed: {stats['documents_failed']}")
        logger.info(f"Total chunks created: {stats['total_chunks_created']}")
        logger.info(f"Total errors: {stats['total_errors']}")
        logger.info("=" * 80)

        # Exit with error code if any documents failed
        if stats['documents_failed'] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error during processing: {e}", exc_info=True)
        sys.exit(1)
    finally:
        processor.close()


if __name__ == "__main__":
    main()
