from unittest.mock import MagicMock, patch, call

import pytest

from conftest import make_tool_response, make_text_response
from ai_generator import AIGenerator

# ---------------------------------------------------------------------------
# Fixture: AIGenerator with mocked Anthropic client
# ---------------------------------------------------------------------------


@pytest.fixture
def generator():
    """Return (AIGenerator instance, mock client) with Anthropic patched out."""
    with patch("ai_generator.anthropic.Anthropic"):
        gen = AIGenerator("fake-key", "", "", "fake-model")
    mock_client = MagicMock()
    gen.client = mock_client
    return gen, mock_client


@pytest.fixture
def tool_manager():
    mgr = MagicMock()
    mgr.execute_tool.return_value = "tool result text"
    return mgr


# ---------------------------------------------------------------------------
# Direct response (no tool use)
# ---------------------------------------------------------------------------


def test_direct_response_returns_text(generator):
    gen, mock_client = generator
    mock_client.messages.create.return_value = make_text_response("Direct answer")

    result = gen.generate_response(
        query="What is Python?", tools=None, tool_manager=None
    )

    assert result == "Direct answer"


def test_direct_response_does_not_call_tool_manager(generator):
    gen, mock_client = generator
    mock_client.messages.create.return_value = make_text_response("Direct answer")
    mock_tm = MagicMock()

    gen.generate_response(query="What is Python?", tools=None, tool_manager=mock_tm)

    mock_tm.execute_tool.assert_not_called()


def test_conversation_history_appended_to_system_prompt(generator):
    gen, mock_client = generator
    mock_client.messages.create.return_value = make_text_response("ok")

    gen.generate_response(
        query="Follow-up question",
        conversation_history="User: Hello\nAssistant: Hi",
        tools=None,
        tool_manager=None,
    )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "User: Hello\nAssistant: Hi" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Tool-use path — where content queries fail
# ---------------------------------------------------------------------------


def test_tool_use_triggers_handle_tool_execution(generator, tool_manager):
    gen, mock_client = generator
    tool_resp = make_tool_response("search_course_content", "tu-1", {"query": "python"})
    text_resp = make_text_response("Final answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]

    gen.generate_response(
        query="python question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    tool_manager.execute_tool.assert_called_once()


def test_execute_tool_called_with_correct_args(generator, tool_manager):
    gen, mock_client = generator
    tool_resp = make_tool_response(
        "search_course_content", "tu-2", {"query": "async", "course_name": "Python"}
    )
    text_resp = make_text_response("Answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]

    gen.generate_response(
        query="async question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    tool_manager.execute_tool.assert_called_once_with(
        "search_course_content", query="async", course_name="Python"
    )


def test_second_api_call_includes_tools_for_possible_chaining(generator, tool_manager):
    """The intermediate call re-offers tools so Claude can optionally chain a second search."""
    gen, mock_client = generator
    tool_resp = make_tool_response("search_course_content", "tu-3", {"query": "x"})
    text_resp = make_text_response("Answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]

    gen.generate_response(
        query="content question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert mock_client.messages.create.call_count == 2
    second_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    assert "tools" in second_kwargs
    assert "tool_choice" in second_kwargs


def test_second_api_call_messages_contain_tool_result(generator, tool_manager):
    gen, mock_client = generator
    tool_resp = make_tool_response("search_course_content", "tu-4", {"query": "x"})
    text_resp = make_text_response("Answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]
    tool_manager.execute_tool.return_value = "search results here"

    gen.generate_response(
        query="question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    second_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    messages = second_kwargs["messages"]
    # last message is the tool result
    last_msg = messages[-1]
    assert last_msg["role"] == "user"
    tool_result_block = last_msg["content"][0]
    assert tool_result_block["type"] == "tool_result"
    assert tool_result_block["tool_use_id"] == "tu-4"
    assert tool_result_block["content"] == "search results here"


def test_second_api_call_messages_include_assistant_turn(generator, tool_manager):
    gen, mock_client = generator
    tool_resp = make_tool_response("search_course_content", "tu-5", {"query": "x"})
    text_resp = make_text_response("Answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]

    gen.generate_response(
        query="question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    second_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    messages = second_kwargs["messages"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] is tool_resp.content


def test_final_response_text_returned(generator, tool_manager):
    gen, mock_client = generator
    tool_resp = make_tool_response("search_course_content", "tu-6", {"query": "x"})
    text_resp = make_text_response("The final synthesized answer")
    mock_client.messages.create.side_effect = [tool_resp, text_resp]

    result = gen.generate_response(
        query="question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert result == "The final synthesized answer"


# ---------------------------------------------------------------------------
# Exception propagation
# ---------------------------------------------------------------------------


def test_api_exception_propagates_from_generate_response(generator):
    gen, mock_client = generator
    mock_client.messages.create.side_effect = RuntimeError("API failure")

    with pytest.raises(RuntimeError, match="API failure"):
        gen.generate_response(query="test", tools=None, tool_manager=None)


# ---------------------------------------------------------------------------
# Two-round tool-use path
# ---------------------------------------------------------------------------


def _two_round_side_effects():
    """Return (tool_resp_1, tool_resp_2, text_resp) for two-round tests."""
    tool_resp_1 = make_tool_response(
        "search_course_content", "tu-r1", {"query": "first"}
    )
    tool_resp_2 = make_tool_response(
        "search_course_content", "tu-r2", {"query": "second"}
    )
    text_resp = make_text_response("Two-round final answer")
    return tool_resp_1, tool_resp_2, text_resp


def test_two_tool_rounds_makes_three_api_calls(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1, tool_resp_2, text_resp = _two_round_side_effects()
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert mock_client.messages.create.call_count == 3


def test_intermediate_call_includes_tools(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1, tool_resp_2, text_resp = _two_round_side_effects()
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    second_kwargs = mock_client.messages.create.call_args_list[1].kwargs
    assert "tools" in second_kwargs
    assert "tool_choice" in second_kwargs


def test_synthesis_call_after_two_rounds_excludes_tools(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1, tool_resp_2, text_resp = _two_round_side_effects()
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    third_kwargs = mock_client.messages.create.call_args_list[2].kwargs
    assert "tools" not in third_kwargs
    assert "tool_choice" not in third_kwargs


def test_two_tool_rounds_executes_both_tools(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1 = make_tool_response(
        "search_course_content", "tu-r1", {"query": "first"}
    )
    tool_resp_2 = make_tool_response(
        "get_course_outline", "tu-r2", {"course_name": "Python"}
    )
    text_resp = make_text_response("Two-round final answer")
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}, {"name": "get_course_outline"}],
        tool_manager=tool_manager,
    )

    assert tool_manager.execute_tool.call_count == 2
    tool_manager.execute_tool.assert_any_call("search_course_content", query="first")
    tool_manager.execute_tool.assert_any_call(
        "get_course_outline", course_name="Python"
    )


def test_two_tool_rounds_returns_final_text(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1, tool_resp_2, text_resp = _two_round_side_effects()
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    result = gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert result == "Two-round final answer"


def test_messages_accumulate_across_two_rounds(generator, tool_manager):
    gen, mock_client = generator
    tool_resp_1, tool_resp_2, text_resp = _two_round_side_effects()
    mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, text_resp]

    gen.generate_response(
        query="multi-step question",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    # Third call (synthesis) should have 5 messages:
    # user, assistant(tool_use_1), user(tool_result_1), assistant(tool_use_2), user(tool_result_2)
    third_kwargs = mock_client.messages.create.call_args_list[2].kwargs
    messages = third_kwargs["messages"]
    assert len(messages) == 5
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[3]["role"] == "assistant"
    assert messages[4]["role"] == "user"
    assert messages[4]["content"][0]["type"] == "tool_result"
