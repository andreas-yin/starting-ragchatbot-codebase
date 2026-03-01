from unittest.mock import MagicMock

import pytest

from conftest import make_search_results
from search_tools import CourseSearchTool
from vector_store import SearchResults

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_execute_returns_formatted_results():
    store = MagicMock()
    store.search.return_value = make_search_results(
        docs=["Content about Python", "More Python content"],
        metas=[
            {"course_title": "Python Basics", "lesson_number": 1},
            {"course_title": "Python Basics", "lesson_number": 2},
        ],
    )
    store.get_lesson_link.return_value = "http://example.com/lesson"

    tool = CourseSearchTool(store)
    result = tool.execute(query="Python")

    assert "Python Basics" in result
    assert "Content about Python" in result
    assert "More Python content" in result


def test_formatted_results_include_header_prefix():
    store = MagicMock()
    store.search.return_value = make_search_results(
        docs=["Some content"],
        metas=[{"course_title": "My Course", "lesson_number": 3}],
    )
    store.get_lesson_link.return_value = None

    tool = CourseSearchTool(store)
    result = tool.execute(query="something")

    assert "[My Course - Lesson 3]" in result


def test_last_sources_populated_after_search():
    store = MagicMock()
    store.search.return_value = make_search_results(
        docs=["Content"],
        metas=[{"course_title": "Test Course", "lesson_number": 1}],
    )
    store.get_lesson_link.return_value = "http://example.com"

    tool = CourseSearchTool(store)
    tool.execute(query="test")

    assert len(tool.last_sources) == 1
    assert tool.last_sources[0]["label"] == "Test Course - Lesson 1"
    assert tool.last_sources[0]["url"] == "http://example.com"


# ---------------------------------------------------------------------------
# Empty / missing results
# ---------------------------------------------------------------------------


def test_execute_empty_results_returns_no_content_message():
    store = MagicMock()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool = CourseSearchTool(store)
    result = tool.execute(query="something")

    assert "No relevant content found" in result


def test_empty_results_with_course_filter_mentions_course():
    store = MagicMock()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool = CourseSearchTool(store)
    result = tool.execute(query="something", course_name="Python Basics")

    assert "No relevant content found" in result
    assert "Python Basics" in result


def test_last_sources_empty_when_no_results():
    store = MagicMock()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool = CourseSearchTool(store)
    tool.execute(query="something")

    assert tool.last_sources == []


# ---------------------------------------------------------------------------
# Error path — key for the "query failed" hypothesis
# ---------------------------------------------------------------------------


def test_execute_returns_error_string_from_store():
    store = MagicMock()
    error_msg = (
        "Search error: n_results cannot be greater than "
        "the number of elements in the index"
    )
    store.search.return_value = SearchResults.empty(error_msg)

    tool = CourseSearchTool(store)
    result = tool.execute(query="something")

    assert result == error_msg


def test_store_called_with_correct_filters():
    store = MagicMock()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool = CourseSearchTool(store)
    tool.execute(query="Python", course_name="Python Basics", lesson_number=2)

    store.search.assert_called_once_with(
        query="Python", course_name="Python Basics", lesson_number=2
    )


def test_execute_with_no_lesson_number_passes_none():
    store = MagicMock()
    store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])

    tool = CourseSearchTool(store)
    tool.execute(query="Python", course_name="Python Basics")

    store.search.assert_called_once_with(
        query="Python", course_name="Python Basics", lesson_number=None
    )
