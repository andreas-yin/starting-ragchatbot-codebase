# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies (first time)
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY

# Start the server (from repo root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

App runs at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

All backend commands must be run from the `backend/` directory (or via `uv run` from root), since the Python modules import each other without a package prefix.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `ANTHROPIC_BASE_URL` | No | Override for OpenRouter or other proxies |
| `ANTHROPIC_AUTH_TOKEN` | No | Auth token when using a proxy |

## Architecture

This is a RAG chatbot where Claude uses a search tool to query a ChromaDB vector store before answering. The entire backend lives in `backend/` as flat Python modules (no package structure).

**Query flow:**
1. `app.py` receives `POST /api/query` → calls `RAGSystem.query()`
2. `RAGSystem` fetches session history, builds the prompt, passes tool definitions to `AIGenerator`
3. `AIGenerator` makes a first Claude API call with `tool_choice: auto`
4. If Claude calls `search_course_content`, `CourseSearchTool` runs a semantic search in ChromaDB; the result is fed back in a second Claude API call (without tools) to synthesize the final answer
5. Sources are stashed on `CourseSearchTool.last_sources` during search and retrieved by `RAGSystem` after `generate_response()` returns

**Key design decisions:**
- Session history is injected into the **system prompt** as a plain-text block, not as message-array turns
- The system prompt limits Claude to **one search per query**
- Course deduplication on startup: documents already in ChromaDB (matched by course title) are skipped
- ChromaDB uses two collections: `course_catalog` (one doc per course, for fuzzy name resolution) and `course_content` (chunked lesson text, for semantic search)
- Course name filtering uses a vector search against `course_catalog` first, then filters `course_content` by the resolved exact title

**Document format expected in `docs/`:**
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<lesson content>

Lesson 1: <title>
...
```

## Configuration

All tuneable parameters are in `backend/config.py`:
- `CHUNK_SIZE = 800` — max characters per chunk
- `CHUNK_OVERLAP = 100` — overlap between adjacent chunks
- `MAX_RESULTS = 5` — top-k results returned by ChromaDB
- `MAX_HISTORY = 2` — conversation turns retained per session (stores `MAX_HISTORY * 2` messages)
- `ANTHROPIC_MODEL = "claude-sonnet-4-20250514"`
- `CHROMA_PATH = "./chroma_db"` — relative to `backend/`, persisted on disk

## Adding New Tools

Tools follow the `Tool` ABC in `search_tools.py`. Implement `get_tool_definition()` (returns an Anthropic tool schema dict) and `execute(**kwargs)`. Register with `tool_manager.register_tool(your_tool)` in `RAGSystem.__init__()`.
