# Code Quality Changes

## Overview

Added Black for automatic Python code formatting and a development script for running quality checks.

## Changes Made

### 1. Added Black as a dev dependency (`pyproject.toml`)

- Added `black>=26.1.0` to the `[dependency-groups] dev` section.
- Added `[tool.black]` configuration:
  - `line-length = 88` (Black default)
  - `target-version = ["py313"]`

### 2. Formatted all Python files with Black

Black reformatted 11 files in `backend/`:

- `backend/ai_generator.py`
- `backend/app.py`
- `backend/models.py`
- `backend/rag_system.py`
- `backend/search_tools.py`
- `backend/session_manager.py`
- `backend/vector_store.py`
- `backend/tests/conftest.py`
- `backend/tests/test_ai_generator.py`
- `backend/tests/test_course_search_tool.py`
- `backend/tests/test_rag_system_query.py`

### 3. Created quality check script (`scripts/quality.sh`)

A shell script to run Black in check mode (no changes applied, exits non-zero if formatting differs). Run with:

```bash
./scripts/quality.sh
```

To auto-format instead:

```bash
uv run black backend/
```
