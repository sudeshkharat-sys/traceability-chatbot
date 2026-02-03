# Generic Data Loader for Document Processing

A modular, generic document processing pipeline that converts documents, creates embeddings, and stores them in OpenSearch with PostgreSQL state tracking.

## Overview

This data loader implements a **two-process pipeline**:

1. **Scrape Process**: Scans filesystem for documents and registers them in PostgreSQL
2. **Create Embedding Process**: Processes documents, generates embeddings, and upserts to OpenSearch

### Key Features

- ✅ **Generic & Modular**: Works with any document type and index
- ✅ **Duplicate Detection**: Uses hash-based deduplication for both documents and chunks
- ✅ **Smart Upsert**: Updates only when content changes, skips unchanged chunks
- ✅ **State Tracking**: PostgreSQL tracks processing status and chunk metadata
- ✅ **Vector Storage**: OpenSearch stores document embeddings for semantic search
- ✅ **Incremental Processing**: Only processes new or modified documents

## Architecture

```
┌─────────────────┐
│   File System   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ Scrape Process  │─────▶│  scraped_docs    │
│  - Scan files   │      │  (PostgreSQL)    │
│  - Hash files   │      │  - status: incomplete
└─────────────────┘      └────────┬─────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Create Embedding│
                         │    Process      │
                         │  - Convert doc  │
                         │  - Chunk text   │
                         │  - Generate emb │
                         │  - Upsert       │
                         └────┬───────┬────┘
                              │       │
                    ┌─────────┘       └─────────┐
                    ▼                           ▼
            ┌──────────────┐          ┌──────────────┐
            │  chunks      │          │  OpenSearch  │
            │ (PostgreSQL) │          │  - embeddings│
            │ - chunk hash │          │  - vectors   │
            │ - metadata   │          │  - metadata  │
            └──────────────┘          └──────────────┘
```

## Database Schema

### scraped_docs Table
Tracks documents to be processed:
- `id`: Auto-incrementing primary key
- `index_name`: OpenSearch index name
- `doc_name`: Document filename
- `doc_path`: Full path to document
- `doc_hash`: SHA256 hash of file content
- `status`: Processing status (`incomplete` / `complete`)
- `created_at`, `updated_at`: Timestamps

### chunks Table
Stores processed document chunks:
- `chunk_id`: Auto-incrementing primary key
- `doc_id`: Foreign key to scraped_docs
- `index_name`: OpenSearch index name
- `chunk_hash`: SHA256 hash of chunk content + metadata
- `chunk_text`: The text content
- `chunk_metadata`: JSON metadata
- `opensearch_id`: ID in OpenSearch
- `created_at`, `updated_at`: Timestamps

## Installation

### Prerequisites

1. **Python 3.9+**
2. **PostgreSQL** (for state tracking)
3. **OpenSearch** (for vector storage)
4. **Azure OpenAI** (for embeddings)

### Install Dependencies

```bash
cd /path/to/nashik-chatbot-pq
pip install -r requirements.txt
```

### Configure Environment

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
```bash
# Azure OpenAI (required)
AZURE_API_KEY=your_key_here
AZURE_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com/openai/deployments/text-embedding-ada-002

# PostgreSQL (required)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# OpenSearch (required)
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=  # Optional
OPENSEARCH_PASSWORD=  # Optional
OPENSEARCH_USE_SSL=false
OPENSEARCH_INDEX_NAME=documents
```

3. Configure paths in `config.yaml`:
```yaml
base_dir: /path/to/your/documents
input_root: /path/to/your/documents/input
output_root: /path/to/your/documents/output
artifacts_path: /path/to/docling_models
```

## Usage

The data loader has three main commands:

### 1. Scrape Process Only

Scan filesystem and register documents for processing:

```bash
cd dataloader
python main.py scrape --directory /path/to/docs --index-name my_index
```

**Options:**
- `--directory`, `-d`: Directory to scrape (required)
- `--index-name`, `-i`: OpenSearch index name (required)
- `--extensions`, `-e`: File extensions (default: `.pdf`)
- `--no-recursive`: Don't scan subdirectories

**Example:**
```bash
python main.py scrape \
  --directory /data/documents/pdfs \
  --index-name technical_docs \
  --extensions .pdf .docx \
  --no-recursive
```

### 2. Create Embedding Process Only

Process all incomplete documents and create embeddings:

```bash
cd dataloader
python main.py create-embedding
```

This will:
1. Query `scraped_docs` for all documents with `status = 'incomplete'`
2. For each document:
   - Convert using Docling
   - Chunk the content
   - Generate embeddings using Azure OpenAI
   - Check if chunks exist (by hash)
   - Upsert to OpenSearch (skip if unchanged)
   - Upsert to PostgreSQL chunks table
   - Update document status to `complete`

**Duplicate Detection Logic:**
- **Same hash**: Chunk is skipped (no change)
- **Different hash**: Chunk is updated in both OpenSearch and PostgreSQL
- **New chunk**: Inserted into both systems

### 3. Full Pipeline

Run both processes sequentially:

```bash
cd dataloader
python main.py full \
  --directory /path/to/docs \
  --index-name my_index
```

This runs:
1. Scrape process → registers documents
2. Create embedding process → processes all incomplete documents

## Workflow Examples

### First-Time Setup

```bash
# 1. Configure environment
cp .env.example .env
vim .env  # Add your credentials

# 2. Edit config.yaml with your paths
vim config.yaml

# 3. Initialize database (creates tables)
cd /path/to/nashik-chatbot-pq
python -c "from app.connectors.state_db_manager import StateDBManager; from app.config.config import get_settings; settings = get_settings(); StateDBManager.create_database_if_not_exists(settings.POSTGRES_HOST, settings.POSTGRES_PORT, settings.POSTGRES_USER, settings.POSTGRES_PASSWORD, settings.POSTGRES_DB); StateDBManager.initialize_database(settings.postgres_url)"

# 4. Run full pipeline
cd dataloader
python main.py full --directory /data/documents --index-name docs
```

### Incremental Updates

When you add new documents to your directory:

```bash
# Scrape new files
python main.py scrape --directory /data/documents --index-name docs

# Process only new documents
python main.py create-embedding
```

### Reprocessing Documents

If you need to reprocess specific documents:

```sql
-- Reset document status in PostgreSQL
UPDATE scraped_docs SET status = 'incomplete' WHERE id = 123;
```

Then run:
```bash
python main.py create-embedding
```

## Document Processing Pipeline

### Document Conversion (Docling)

The system uses [Docling](https://github.com/DS4SD/docling) for document understanding:

1. **PDF Processing**:
   - Extracts text with layout preservation
   - Detects tables (with structure extraction)
   - Identifies figures/images
   - Generates page images

2. **Visual Language Model (VLM)**:
   - Describes pictures and figures
   - Uses SmolDocling-256M-preview model

3. **Output**:
   - Markdown with embedded images
   - JSON with document structure
   - Individual images (pages, tables, figures)

### Chunking Strategy

Uses **HybridChunker** with:
- OpenAI tokenizer (`cl100k_base`)
- Max tokens: 8191
- Custom serializer for picture descriptions
- Metadata preservation

Each chunk includes:
- Text content
- Page number
- Document structure info
- Picture descriptions (if any)

### Embedding Generation

- **Model**: Azure OpenAI `text-embedding-ada-002`
- **Dimension**: 1536
- **Batch processing**: Multiple chunks embedded in single API call
- **Cost optimization**: Only new/modified chunks are embedded

### OpenSearch Storage

Documents are stored with:
```json
{
  "text": "chunk content",
  "embedding": [0.123, 0.456, ...],  // 1536-dim vector
  "metadata": {
    "page": 1,
    "section": "Introduction"
  },
  "doc_name": "document.pdf",
  "doc_id": 123,
  "doc_hash": "sha256_hash"
}
```

## Logging

All processes log to console with format:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Log levels:**
- `INFO`: Progress updates
- `DEBUG`: Detailed operation info
- `WARNING`: Skipped items or minor issues
- `ERROR`: Failed operations

**Key log messages:**
- ✅ `"Inserted document: ..."` → New document registered
- ✅ `"Created chunk ..."` → New chunk added
- 🔄 `"Updated chunk ..."` → Chunk content changed
- ⏭️ `"Skipped chunk ..."` → Chunk unchanged
- ✅ `"Updated document status to 'complete'"` → Processing finished

## Troubleshooting

### Issue: "Document not found"
**Cause**: File was moved/deleted after scraping
**Solution**: Re-run scrape process or remove from database

### Issue: "Failed to connect to OpenSearch"
**Cause**: OpenSearch not running or wrong credentials
**Solution**:
```bash
# Check if OpenSearch is running
curl http://localhost:9200

# Check credentials in .env
```

### Issue: "Azure OpenAI rate limit"
**Cause**: Too many embedding requests
**Solution**: Add retry logic or reduce batch size in code

### Issue: Database connection errors
**Cause**: PostgreSQL credentials or connection issues
**Solution**:
```bash
# Test connection
psql -h localhost -U postgres -d chatbot

# Check .env settings
```

## Advanced Configuration

### Custom File Extensions

Edit `config.yaml`:
```yaml
files:
  extensions:
    - .pdf
    - .docx
    - .txt
    - .md
```

### Custom Chunking

Edit `config.yaml`:
```yaml
chunking:
  max_tokens: 4096  # Smaller chunks
  overlap_tokens: 100  # Add overlap
```

### Custom OpenSearch Mapping

Edit `config.yaml` to change vector dimensions or index settings:
```yaml
opensearch:
  index_mapping:
    properties:
      embedding:
        dimension: 3072  # For different embedding model
```

## File Structure

```
dataloader/
├── main.py                      # Main entry point
├── scrape_process.py            # File scanning & registration
├── create_embedding_process.py  # Document processing & embedding
├── document_processor.py        # Original Docling conversion (legacy)
├── pipeline_factory.py          # Document converter & chunker factory
├── serializers.py              # Custom chunk serializers
├── config.py                   # Path configuration (legacy)
├── config.yaml                 # New YAML configuration
└── README.md                   # This file

app/
├── connectors/
│   ├── opensearch_connector.py  # OpenSearch client
│   ├── state_db_connector.py    # PostgreSQL client
│   └── table_creation.py        # Database schema
└── config/
    └── config.py               # Environment configuration
```

## Migration from Old System

If you're migrating from the old `main.py`:

**Old way:**
```bash
python main.py  # Processes all PDFs, no state tracking
```

**New way:**
```bash
# Step 1: Register files
python main.py scrape --directory /input --index-name docs

# Step 2: Process with state tracking
python main.py create-embedding
```

**Benefits:**
- State persistence (resume after failures)
- Duplicate detection (no reprocessing)
- Incremental updates (only new documents)
- Database storage (queryable chunks)

## Contributing

To extend the data loader:

1. **Add new document types**: Update `pipeline_factory.py`
2. **Customize chunking**: Modify `serializers.py`
3. **Add metadata enrichment**: Edit `create_embedding_process.py`
4. **Change embedding model**: Update `.env` and `config.py`

## Support

For issues or questions:
1. Check logs for error messages
2. Verify `.env` configuration
3. Test database connections
4. Ensure OpenSearch is running
