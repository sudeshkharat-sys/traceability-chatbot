# Knowledge Transfer Guide — Nashik Quality Intelligence Chatbot

*A simple-language guide to what each part of this project does, why it exists, and how it helps the user.*

---

## 1. What is this project? (The Big Picture)

This is an **AI chatbot for vehicle quality data** (Thar Roxx project). A quality engineer can ask questions in plain English like:

> "Show me the top 5 warranty issues for the door assembly last month"

...and the chatbot will:
1. Understand the question,
2. Fetch the answer from the right database,
3. Reply with text, tables, and charts.

Instead of engineers digging through Excel sheets and reports, they just **chat**.

### The three kinds of "brains" (databases) it uses

| Database | What it stores | Why this type of DB |
|----------|----------------|---------------------|
| **Neo4j** (Graph DB) | Traceability data — which part went into which chassis, on which line, on which date | Traceability is all about *relationships* (part → chassis → line → supplier). Graph DBs are built for exactly that. |
| **OpenSearch** (Vector DB) | 200+ PDF quality guidelines & SOPs, converted to "embeddings" | Lets the bot find documents by *meaning*, not just keywords. Ask "how to fix paint peeling" and it finds the right guideline even if it never uses those exact words. |
| **PostgreSQL** (Relational DB) | Users, login info, chat history, conversation memory, and raw warranty/Part Labeler data | Standard, reliable storage for tables and app state. |

The AI itself is **Azure OpenAI (GPT-4o)** — the code sends the question plus the data to GPT-4o, and GPT-4o writes the answer.

---

## 2. How a question travels through the system (End-to-End Flow)

```
User types question in the React web page (frontend/)
        │
        ▼
Nginx (SSL/HTTPS proxy) forwards it to the backend
        │
        ▼
FastAPI backend (main.py + backend/api/) receives it
        │
        ▼
Agent Pool (app/agents/agent_pool.py) picks the right "agent"
        │
        ▼
The agent uses its tools:
   - writes a Cypher query for Neo4j, OR
   - runs a SQL query on PostgreSQL, OR
   - does a vector search in OpenSearch
        │
        ▼
GPT-4o turns the raw data into a friendly answer (+ chart data)
        │
        ▼
Answer streams back to the browser, chat history saved in PostgreSQL
```

---

## 3. Folder-by-Folder Guide

### `main.py` — The Starting Point
- **What:** The file that starts the whole application (FastAPI server).
- **What it does:** On startup it initializes databases, creates tables, loads prompts, and runs migrations (`StartupInitializer`). It also serves the built React frontend, so one server hosts both the API and the UI.
- **How it helps:** One command (`python main.py` or Docker) brings everything up.

### `app/agents/` — The AI Brains (Most Important Folder)
Each "agent" is a specialist AI worker. `agent_pool.py` is the manager that creates the right agent for each conversation.

| Agent file | What it is for | How it helps the user |
|------------|----------------|------------------------|
| `analyst_agent.py` | The **main quality analyst**. Queries Neo4j traceability data and explains results with insights and charts. | Answers "which parts / which chassis / what trend" questions. |
| `cypher_agent.py` | Translates plain English into **Cypher** (Neo4j's query language). | The user never needs to know Cypher. |
| `standards_guidelines_agent.py` | Searches the PDF guidelines stored in OpenSearch. | Answers "what does the standard say about X" with citations. |
| `qlense_agent.py` | Two-phase agent: first **finds quality issues** from the DB, then (if the user says yes) **retrieves solutions** from the Problem-Solved knowledge base. | Problem + fix suggestion in one conversation. |
| `part_labeler_dashboard_agent.py` | Runs read-only SQL on Part Labeler tables (warranty, RPT, GNOVAC, RFI, e-SQA). | Analytics for the Part Sense Visualizer module. |
| `part_labeler_chart_agent.py` | Builds chart data for Part Labeler dashboards. | Turns numbers into visual trends. |
| `checkpointer_manager.py` | Saves conversation memory into PostgreSQL. | The bot **remembers** earlier messages, even after a restart. |
| `agent_pool.py` | Factory/manager: given a conversation and agent type, hands out the right agent with memory attached. | Keeps agent creation in one place — add new agents here. |

**Common features all agents share:** a "think" scratchpad tool, a to-do list middleware (plans multi-step answers), and automatic **summarization** — if a chat gets very long (~100K tokens), old messages are summarized so the conversation can continue without hitting AI limits.

### `app/tools/` — The Agents' Toolbox
Tools are the "hands" the AI uses to actually do things:

| Tool | What it does |
|------|--------------|
| `pg_query_tool.py` | Runs **SELECT-only** SQL on PostgreSQL (read-only for safety). |
| `pg_schema_tool.py` | Tells the AI what tables/columns exist, so it writes correct SQL. |
| `vector_db_tool.py` | Searches guidelines in OpenSearch by meaning. |
| `qlense_search_tool.py` | Fixed (pre-written, safe) SQL search for quality issues. |
| `chart_generator_tool.py` | Produces chart data the frontend can draw. |
| `think_tool.py` | A private notepad where the AI reasons before answering. |

### `app/prompts/` — The Agents' Instructions
Each file holds the **system prompt** (the rulebook) for one agent — its personality, its job, the rules it must follow. **Why separate files:** to change how an agent behaves, you edit its prompt here; no code logic changes needed.

### `app/connectors/` — Database Plumbing
One file per database (`neo4j_connector.py`, `opensearch_connector.py`, `state_db_connector.py`, etc.), plus `migrations.py` (safe, repeatable schema updates) and `table_creation.py`. **Why:** all connection details live in one layer. If a DB moves or changes, you fix it here only.

### `app/queries/` — Pre-written SQL/Cypher
Reusable queries for auth, chat history, Part Labeler, Z-Stage, etc., plus `query_validator.py` which **blocks dangerous queries** (safety layer so the AI can't damage data).

### `app/models/` — LLM Connection
`azure_openai_handler.py` and `model_factory.py` handle talking to Azure OpenAI. **Why a factory:** if the company switches AI providers/models, only this folder changes.

### `app/services/` — Startup & Prompt Management
- `startup_initializer.py`: runs all the "get ready" steps when the app boots.
- `prompt_manager.py`: loads/serves prompts (stored in DB so they can be updated without redeploying).

### `app/chat_history/` — Conversation Records
`chat_manager.py` saves and loads chat conversations, so users see their past chats in the sidebar.

### `app/utils/` — Small Helpers
Formatting query results, formatting chart data, executing queries — shared helper code.

### `backend/` — The Web API Layer
FastAPI routes = the "doors" the frontend knocks on:

| Route folder | Purpose |
|--------------|---------|
| `auth/` | Login, signup, tokens (JWT). |
| `conversations/` | Start chats, send messages, get history. |
| `admin/` | Admin panel — manage users, assign roles. |
| `part_labeler_routes.py` | Part Sense Visualizer APIs (uploads, mapping data). |
| `z_satge/` | Z-Stage module: layouts, station boxes, car models, layered audits, 3D models. |
| `health/` | "Is the app alive?" check for monitoring. |

`backend/models/schemas/` holds Pydantic schemas — they define exactly what request/response data must look like, catching bad input early.

### `frontend/` — What the User Sees
React app. Key components: `ChatPage`/`ChatArea`/`ChatMessage` (the chat UI), `ChartComponent` (draws graphs with Recharts), `CitationsTable` + `PdfViewerModal` (shows which guideline PDF an answer came from and opens it), `ThinkingStepsDisplay` (shows the AI's live progress steps), `Sidebar` (past conversations), `AdminPanel`, `PartLabeler`, `ZStage`.

### `dataloader/` — Getting PDFs into the Bot
Pipeline for **unstructured** documents: scrape PDFs → split into chunks → create embeddings → store in OpenSearch. Run once when new guideline documents arrive.

### `scripts/` — Getting Structured Data In
- `data_loading.py`: bulk-loads CSV traceability data into Neo4j (built for millions of rows).
- `process_warranty.py` / `filter_warranty_data.py`: prepare warranty data for Part Labeler.
- `create_users.py`: create admin / part_labeler users (these can't sign up publicly).

### `tasks.py`, `Dockerfile`, `docker-compose.yml`, `nginx.conf`, `ssl/`
- `tasks.py`: shortcut commands (`invoke scrape-documents`, `invoke create-embeddings`, `invoke process-warranty-data`).
- Docker files: package and run the whole stack with one command.
- Nginx + ssl/: HTTPS security and traffic routing in production.

---

## 4. User Roles

| Role | Can do |
|------|--------|
| `admin` | Everything + Admin Panel (manage users) |
| `user` | All chat features (default on signup) |
| `part_labeler` | Only the Part Sense Visualizer screens |

---

## 5. How this helps the end user (Summary)

1. **No technical skills needed** — ask in plain English; the AI writes the Cypher/SQL.
2. **One place for everything** — traceability, warranty, guidelines, and dashboards in one chat window.
3. **Trustworthy answers** — guideline answers come with citations and a PDF viewer; queries are read-only and validated.
4. **Remembers context** — follow-up questions like "and for last month?" work, because conversations have memory.
5. **Visual insights** — charts and tables, not just text.

---

## 6. Common Maintenance Tasks (Quick Reference)

| Task | Where to go |
|------|-------------|
| Change how an agent answers | `app/prompts/` (edit its prompt) |
| Add a new agent | Prompt in `app/prompts/` → class in `app/agents/` → register in `agent_pool.py` (see README "How to Add a New Agent") |
| Load new traceability CSVs | `csv_data/` + `scripts/data_loading.py` |
| Add new guideline PDFs | `documents/` + `invoke scrape-documents` + `invoke create-embeddings` |
| Create an admin user | `scripts/create_users.py` |
| DB connection issues | `app/connectors/` + `.env` |
| Change UI | `frontend/src/components/` |
| Deploy | `docker compose up -d --build` |
