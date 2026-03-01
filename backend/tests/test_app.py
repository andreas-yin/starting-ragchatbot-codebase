"""
API endpoint tests for the RAG chatbot.

The production app.py mounts static files from ../frontend which doesn't exist
in the test environment, so we define a minimal test app inline that mirrors
the same endpoint logic and use FastAPI's TestClient against it.
"""
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic models — identical to those in app.py
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_app(rag) -> FastAPI:
    """Return a minimal FastAPI app wired to *rag* (a mock or real RAGSystem)."""
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag.session_manager.create_session()
            answer, sources = rag.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag.session_manager.clear_session(session_id)
        return {"status": "ok"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag(mock_rag_system):
    """Alias the shared conftest fixture under a shorter name."""
    return mock_rag_system


@pytest.fixture
def client(mock_rag):
    return TestClient(_make_app(mock_rag))


# ---------------------------------------------------------------------------
# POST /api/query — happy path
# ---------------------------------------------------------------------------

def test_query_returns_200(client):
    resp = client.post("/api/query", json={"query": "What is Python?", "session_id": "s1"})
    assert resp.status_code == 200


def test_query_response_contains_answer(client):
    resp = client.post("/api/query", json={"query": "What is Python?", "session_id": "s1"})
    assert resp.json()["answer"] == "Test answer"


def test_query_response_contains_sources(client):
    resp = client.post("/api/query", json={"query": "What is Python?", "session_id": "s1"})
    sources = resp.json()["sources"]
    assert isinstance(sources, list)
    assert sources[0]["label"] == "Course A - Lesson 1"
    assert sources[0]["url"] == "http://example.com"


def test_query_echoes_session_id(client):
    resp = client.post("/api/query", json={"query": "test", "session_id": "my-session"})
    assert resp.json()["session_id"] == "my-session"


def test_query_calls_rag_with_correct_args(client, mock_rag):
    client.post("/api/query", json={"query": "What is Python?", "session_id": "s1"})
    mock_rag.query.assert_called_once_with("What is Python?", "s1")


# ---------------------------------------------------------------------------
# POST /api/query — auto session creation
# ---------------------------------------------------------------------------

def test_query_without_session_id_creates_session(client, mock_rag):
    resp = client.post("/api/query", json={"query": "test"})
    assert resp.status_code == 200
    mock_rag.session_manager.create_session.assert_called_once()


def test_query_without_session_id_returns_generated_id(client):
    resp = client.post("/api/query", json={"query": "test"})
    assert resp.json()["session_id"] == "auto-created-session"


# ---------------------------------------------------------------------------
# POST /api/query — validation & error handling
# ---------------------------------------------------------------------------

def test_query_missing_query_field_returns_422(client):
    resp = client.post("/api/query", json={"session_id": "s1"})
    assert resp.status_code == 422


def test_query_returns_500_when_rag_raises(client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("Something went wrong")
    resp = client.post("/api/query", json={"query": "test", "session_id": "s1"})
    assert resp.status_code == 500


def test_query_500_response_includes_error_detail(client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("Something went wrong")
    resp = client.post("/api/query", json={"query": "test", "session_id": "s1"})
    assert "Something went wrong" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/courses — happy path
# ---------------------------------------------------------------------------

def test_courses_returns_200(client):
    assert client.get("/api/courses").status_code == 200


def test_courses_returns_correct_total(client):
    assert client.get("/api/courses").json()["total_courses"] == 2


def test_courses_returns_titles_list(client):
    titles = client.get("/api/courses").json()["course_titles"]
    assert "Python Basics" in titles
    assert "Advanced Python" in titles


def test_courses_calls_get_course_analytics(client, mock_rag):
    client.get("/api/courses")
    mock_rag.get_course_analytics.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/courses — error handling
# ---------------------------------------------------------------------------

def test_courses_returns_500_when_analytics_raises(client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("DB error")
    assert client.get("/api/courses").status_code == 500


def test_courses_500_includes_error_detail(client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("DB error")
    assert "DB error" in client.get("/api/courses").json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

def test_delete_session_returns_200(client):
    assert client.delete("/api/session/some-session").status_code == 200


def test_delete_session_returns_ok_body(client):
    assert client.delete("/api/session/some-session").json() == {"status": "ok"}


def test_delete_session_calls_clear_session(client, mock_rag):
    client.delete("/api/session/target-session")
    mock_rag.session_manager.clear_session.assert_called_once_with("target-session")
