"""
Generic Data Loader - Main Entry Point
Orchestrates the document processing pipeline with two main processes:
1. Scrape Process: Index files from filesystem
2. Create Embedding Process: Process documents, create embeddings, and upsert to OpenSearch
"""

import logging
import argparse
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))

from scrape_process import scrape_files
from create_embedding_process import create_embeddings

logger = logging.getLogger(__name__)


def main():
    """
    Main entry point for the data loader
    """
    parser = argparse.ArgumentParser(
        description="Generic Data Loader for Document Processing and Embedding Creation"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape files from directory and register for processing"
    )
    scrape_parser.add_argument(
        "--directory",
        "-d",
        required=True,
        help="Directory to scrape for files",
    )
    scrape_parser.add_argument(
        "--index-name",
        "-i",
        required=True,
        help="Name of the OpenSearch index for these documents",
    )
    scrape_parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        default=[".pdf"],
        help="File extensions to include (e.g., .pdf .docx)",
    )
    scrape_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories recursively",
    )

    # Create-embedding command
    embed_parser = subparsers.add_parser(
        "create-embedding",
        help="Process incomplete documents and create embeddings"
    )

    # Full pipeline command
    full_parser = subparsers.add_parser(
        "full",
        help="Run full pipeline: scrape + create-embedding"
    )
    full_parser.add_argument(
        "--directory",
        "-d",
        required=True,
        help="Directory to scrape for files",
    )
    full_parser.add_argument(
        "--index-name",
        "-i",
        required=True,
        help="Name of the OpenSearch index for these documents",
    )
    full_parser.add_argument(
        "--extensions",
        "-e",
        nargs="+",
        default=[".pdf"],
        help="File extensions to include (e.g., .pdf .docx)",
    )
    full_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories recursively",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.command == "scrape":
        logger.info("Starting scrape process...")
        stats = scrape_files(
            directory=args.directory,
            index_name=args.index_name,
            file_extensions=args.extensions,
            recursive=not args.no_recursive,
        )

        print(f"\n{'='*60}")
        print("Scraping Results")
        print(f"{'='*60}")
        print(f"Files scanned: {stats['scanned']}")
        print(f"New documents: {stats['new']}")
        print(f"Existing documents: {stats['existing']}")
        print(f"Errors: {stats['errors']}")
        print(f"{'='*60}\n")

    elif args.command == "create-embedding":
        logger.info("Starting create-embedding process...")
        stats = create_embeddings()

        print(f"\n{'='*60}")
        print("Embedding Creation Results")
        print(f"{'='*60}")
        print(f"Documents completed: {stats['documents_completed']}")
        print(f"Documents failed: {stats['documents_failed']}")
        print(f"Total chunks created: {stats['total_chunks_created']}")
        print(f"Total chunks updated: {stats['total_chunks_updated']}")
        print(f"Total chunks skipped: {stats['total_chunks_skipped']}")
        print(f"Total errors: {stats['total_errors']}")
        print(f"{'='*60}\n")

    elif args.command == "full":
        logger.info("Starting full pipeline...")

        # Step 1: Scrape
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Scraping files")
        logger.info("="*60)
        scrape_stats = scrape_files(
            directory=args.directory,
            index_name=args.index_name,
            file_extensions=args.extensions,
            recursive=not args.no_recursive,
        )

        print(f"\nScraping complete: {scrape_stats['new']} new documents registered")

        # Step 2: Create embeddings
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Creating embeddings")
        logger.info("="*60)
        embed_stats = create_embeddings()

        # Final summary
        print(f"\n{'='*60}")
        print("FULL PIPELINE COMPLETE")
        print(f"{'='*60}")
        print("\nScraping Results:")
        print(f"  Files scanned: {scrape_stats['scanned']}")
        print(f"  New documents: {scrape_stats['new']}")
        print(f"  Existing documents: {scrape_stats['existing']}")
        print(f"  Errors: {scrape_stats['errors']}")
        print("\nEmbedding Results:")
        print(f"  Documents completed: {embed_stats['documents_completed']}")
        print(f"  Documents failed: {embed_stats['documents_failed']}")
        print(f"  Total chunks created: {embed_stats['total_chunks_created']}")
        print(f"  Total chunks updated: {embed_stats['total_chunks_updated']}")
        print(f"  Total chunks skipped: {embed_stats['total_chunks_skipped']}")
        print(f"  Total errors: {embed_stats['total_errors']}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
