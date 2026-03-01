from unittest.mock import MagicMock, patch

import pytest

from rag_system import RAGSystem

# ---------------------------------------------------------------------------
# Fixture: RAGSystem with all heavy dependencies mocked out
# ---------------------------------------------------------------------------


@pytest.fixture
def rag_setup():
    """
    Return (rag, mock_ai, mock_session).

    AIGenerator, VectorStore, DocumentProcessor, and SessionManager constructors
    are patched so no real I/O or model loading happens.
    """
    mock_config = MagicMock()
    mock_config.ANTHROPIC_API_KEY = "fake-key"
    mock_config.ANTHROPIC_BASE_URL = ""
    mock_config.ANTHROPIC_AUTH_TOKEN = ""
    mock_config.ANTHROPIC_MODEL = "fake-model"
    mock_config.CHUNK_SIZE = 800
    mock_config.CHUNK_OVERLAP = 100
    mock_config.CHROMA_PATH = "/tmp/test_chroma"
    mock_config.EMBEDDING_MODEL = "fake-embed"
    mock_config.MAX_RESULTS = 5
    mock_config.MAX_HISTORY = 2

    mock_ai = MagicMock()
    mock_ai.generate_response.return_value = "mocked answer"

    mock_session = MagicMock()
    mock_session.get_conversation_history.return_value = None

    with (
        patch("rag_system.AIGenerator", return_value=mock_ai),
        patch("rag_system.VectorStore", return_value=MagicMock()),
        patch("rag_system.DocumentProcessor", return_value=MagicMock()),
        patch("rag_system.SessionManager", return_value=mock_session),
    ):
        rag = RAGSystem(mock_config)

    return rag, mock_ai, mock_session


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_query_returns_response_and_sources(rag_setup):
    rag, mock_ai, _ = rag_setup
    mock_ai.generate_response.return_value = "Test answer"

    result = rag.query("What is Python?")

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] == "Test answer"
    assert isinstance(result[1], list)


def test_query_builds_prompt_with_prefix(rag_setup):
    rag, mock_ai, _ = rag_setup

    rag.query("What is Python?")

    call_kwargs = mock_ai.generate_response.call_args.kwargs
    assert "What is Python?" in call_kwargs["query"]


def test_query_passes_tool_definitions_to_generator(rag_setup):
    rag, mock_ai, _ = rag_setup

    rag.query("something")

    call_kwargs = mock_ai.generate_response.call_args.kwargs
    tools = call_kwargs.get("tools")
    assert tools is not None
    assert isinstance(tools, list)
    assert len(tools) > 0


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------


def test_query_with_session_id_passes_history(rag_setup):
    rag, mock_ai, mock_session = rag_setup
    mock_session.get_conversation_history.return_value = "Previous: User asked about X"

    rag.query("follow-up question", session_id="sess-123")

    mock_session.get_conversation_history.assert_called_once_with("sess-123")
    call_kwargs = mock_ai.generate_response.call_args.kwargs
    assert call_kwargs["conversation_history"] == "Previous: User asked about X"


def test_query_without_session_id_passes_no_history(rag_setup):
    rag, mock_ai, mock_session = rag_setup

    rag.query("standalone question")  # no session_id

    mock_session.get_conversation_history.assert_not_called()
    call_kwargs = mock_ai.generate_response.call_args.kwargs
    assert call_kwargs["conversation_history"] is None


def test_session_exchange_recorded_after_response(rag_setup):
    rag, mock_ai, mock_session = rag_setup
    mock_ai.generate_response.return_value = "The answer"

    rag.query("What is X?", session_id="sess-456")

    mock_session.add_exchange.assert_called_once_with(
        "sess-456", "What is X?", "The answer"
    )


# ---------------------------------------------------------------------------
# Sources lifecycle
# ---------------------------------------------------------------------------


def test_sources_from_search_tool_returned(rag_setup):
    rag, _, _ = rag_setup
    # Simulate that a tool search populated last_sources before query() collects them
    rag.search_tool.last_sources = [
        {"label": "Course A - Lesson 1", "url": "http://a.com"}
    ]

    _, sources = rag.query("question")

    assert sources == [{"label": "Course A - Lesson 1", "url": "http://a.com"}]


def test_sources_reset_after_query(rag_setup):
    rag, _, _ = rag_setup
    rag.search_tool.last_sources = [{"label": "Something", "url": None}]

    rag.query("question")

    assert rag.search_tool.last_sources == []


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_exception_from_generator_propagates(rag_setup):
    """Exceptions from generate_response must bubble up to app.py (no silent swallowing)."""
    rag, mock_ai, _ = rag_setup
    mock_ai.generate_response.side_effect = RuntimeError("API failed")

    with pytest.raises(RuntimeError, match="API failed"):
        rag.query("question")
