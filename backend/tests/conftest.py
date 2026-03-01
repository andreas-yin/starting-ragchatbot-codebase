import sys
from pathlib import Path

# Add backend/ and backend/tests/ to sys.path so modules resolve correctly
_backend_dir = Path(__file__).parent.parent
_tests_dir = Path(__file__).parent
for _p in (_backend_dir, _tests_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pytest
from unittest.mock import MagicMock

from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Plain helper factories (import these directly in test files when needed)
# ---------------------------------------------------------------------------


def make_search_results(docs, metas):
    """Return a SearchResults with the given documents and metadata."""
    return SearchResults(
        documents=docs,
        metadata=metas,
        distances=[0.1] * len(docs),
    )


def make_tool_response(tool_name, tool_id, input_dict):
    """Return a mock Anthropic response with stop_reason='tool_use'."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = input_dict

    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


def make_text_response(text):
    """Return a mock Anthropic response with stop_reason='end_turn'."""
    block = MagicMock()
    block.text = text

    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [block]
    return resp


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_search_results():
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_search_results():
    def _factory(msg):
        return SearchResults.empty(msg)

    return _factory


@pytest.fixture
def mock_vector_store():
    return MagicMock()


@pytest.fixture
def mock_rag_system():
    """Return a fully configured mock RAGSystem for use across test files."""
    mock = MagicMock()
    mock.query.return_value = (
        "Test answer",
        [{"label": "Course A - Lesson 1", "url": "http://example.com"}],
    )
    mock.session_manager.create_session.return_value = "auto-created-session"
    mock.session_manager.get_conversation_history.return_value = None
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Advanced Python"],
    }
    return mock
