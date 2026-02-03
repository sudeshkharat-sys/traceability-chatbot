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

3. Configure document processing paths in `.env`:
```bash
# Document Processing Paths
DOCLING_BASE_DIR=/data/documents
DOCLING_ARTIFACTS_PATH=/data/docling_models/docling_all_models
DOCLING_INPUT_ROOT=/data/documents/input
DOCLING_OUTPUT_ROOT=/data/documents/output
DOCLING_VLM_MODEL=SmolDocling-256M-preview
DOCLING_LAYOUT_MODEL=docling-layout-heron
```

## 🚀 Usage

The data loader is integrated into the project's task system using **Invoke**. All commands are run from the **project root** directory.

### 1. Scrape Documents

Scan filesystem and register documents for processing:

```bash
# Basic usage
invoke scrape-documents --directory=/path/to/docs --index-name=my_index

# With options
invoke scrape-documents \
  --directory=/data/documents/pdfs \
  --index-name=technical_docs \
  --extensions=".pdf,.docx" \
  --no-recursive
```

**Arguments:**
- `--directory`: Directory to scrape (required)
- `--index-name`: OpenSearch index name (required)
- `--extensions`: Comma-separated file extensions (default: `.pdf`)
- `--no-recursive`: Don't scan subdirectories

### 2. Create Embeddings

Process all incomplete documents and create embeddings:

```bash
# Use default index from settings
invoke create-embeddings

# Specify custom index
invoke create-embeddings --index-name=my_index
```

This will:
1. Query `scraped_docs` for all documents with `status = 'incomplete'`
2. For each document:
   - Convert using Docling
   - Chunk the content
   - Generate embeddings using Azure OpenAI (via LangChain)
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
invoke process-documents \
  --directory=/path/to/docs \
  --index-name=my_index
```

This runs:
1. Scrape process → registers documents
2. Create embedding process → processes all incomplete documents

### 4. List Documents

View documents in the scraped_docs table:

```bash
# List all documents
invoke list-documents

# Filter by status
invoke list-documents --status=incomplete

# Filter by index with limit
invoke list-documents --index-name=my_index --limit=20
```

### 5. Reset Document Status

Reprocess documents by resetting their status to incomplete:

```bash
# Reset specific document by ID
invoke reset-document-status --doc-id=5

# Reset all documents in an index
invoke reset-document-status --index-name=my_index
```

## 📋 Workflow Examples

### First-Time Setup

```bash
# 1. Configure environment
cp .env.example .env
vim .env  # Add your credentials

# 2. Configure document paths in .env
# (See DOCLING_* variables in .env.example)

# 3. Initialize database (creates tables)
cd /path/to/nashik-chatbot-pq
invoke setup-database

# 4. Run full pipeline
invoke process-documents --directory=/data/documents --index-name=docs
```

### Incremental Updates

When you add new documents to your directory:

```bash
# Scrape new files
invoke scrape-documents --directory=/data/documents --index-name=docs

# Process only new documents
invoke create-embeddings
```

### Reprocessing Documents

If you need to reprocess specific documents:

```bash
# Reset specific document
invoke reset-document-status --doc-id=123

# Or reset entire index
invoke reset-document-status --index-name=docs
```

Then run:
```bash
invoke create-embeddings
```

### Monitoring Progress

Check document processing status:

```bash
# View incomplete documents
invoke list-documents --status=incomplete

# View completed documents
invoke list-documents --status=complete

# View all documents in an index
invoke list-documents --index-name=docs --limit=50
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

## ⚙️ Advanced Configuration

### Custom File Extensions

When running scrape, specify extensions:
```bash
invoke scrape-documents \
  --directory=/path \
  --index-name=index \
  --extensions=".pdf,.docx,.txt"
```

### Custom Chunking

Edit `pipeline_factory.py` to adjust chunking parameters:
```python
chunker = HybridChunker(
    tokenizer=OpenAITokenizer(
        tokenizer=tiktoken.get_encoding("cl100k_base"),
        max_tokens=4096,  # Smaller chunks
    ),
    # Add overlap if needed
)

## 📁 File Structure

```
dataloader/
├── scrape_process.py            # File scanning & registration
├── create_embedding_process.py  # Document processing & embedding (LangChain)
├── document_processor.py        # Original Docling conversion (standalone legacy)
├── pipeline_factory.py          # Document converter & chunker factory
├── serializers.py              # Custom chunk serializers
└── README.md                   # This file

app/
├── connectors/
│   ├── opensearch_connector.py  # OpenSearch client with LangChain integration
│   ├── state_db_connector.py    # PostgreSQL client
│   ├── state_db_manager.py      # Database initialization & management
│   └── table_creation.py        # Database schema (includes scraped_docs & chunks)
└── config/
    └── config.py               # Centralized environment configuration

tasks.py                         # Invoke tasks for all operations
.env                            # Environment configuration (create from .env.example)
```

## 🔄 Migration from Old System

If you're migrating from the old document processor:

**Old way:**
```bash
cd dataloader
python document_processor.py  # Processes all PDFs, no state tracking
```

**New way (task-based):**
```bash
# From project root
# Step 1: Register files in database
invoke scrape-documents --directory=/input --index-name=docs

# Step 2: Process with state tracking
invoke create-embeddings
```

**Benefits:**
- ✅ State persistence (resume after failures)
- ✅ Duplicate detection (no reprocessing)
- ✅ Incremental updates (only new documents)
- ✅ Database storage (queryable chunks)
- ✅ LangChain integration (automatic embeddings)
- ✅ Task-based management (centralized commands)

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
