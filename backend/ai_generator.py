import anthropic
from typing import List, Optional, Dict, Any


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use **get_course_outline** for outline, structure, or "what lessons" queries — returns title, link, and full lesson list; always include the course link in the response
- Use **search_course_content** for questions about specific course content or educational material
- **Up to two tool calls per query** — use a second call only when the first result reveals a specific information gap
- Synthesize results into accurate, fact-based responses
- If the tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, base_url: str, auth_token: str, model: str):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url or None,
            auth_token=auth_token or None,
        )
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        return response.content[0].text

    def _run_tool_round(self, response, messages: List, tool_manager) -> List:
        """Execute all tool calls in response and append results to messages."""
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return messages

    def _handle_tool_execution(
        self, initial_response, base_params: Dict[str, Any], tool_manager
    ):
        """
        Handle execution of tool calls and get follow-up response.

        Supports up to MAX_TOOL_ROUNDS sequential tool-call rounds.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        messages = base_params["messages"].copy()
        messages.append({"role": "assistant", "content": initial_response.content})
        current_response = initial_response

        for round_num in range(self.MAX_TOOL_ROUNDS):
            messages = self._run_tool_round(current_response, messages, tool_manager)

            if round_num < self.MAX_TOOL_ROUNDS - 1:
                # Not the last round — offer tools again so Claude can chain
                intermediate_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": base_params["system"],
                    "tools": base_params["tools"],
                    "tool_choice": {"type": "auto"},
                }
                intermediate_response = self.client.messages.create(
                    **intermediate_params
                )

                if intermediate_response.stop_reason != "tool_use":
                    return intermediate_response.content[0].text

                # Claude called another tool — continue to next round
                messages.append(
                    {"role": "assistant", "content": intermediate_response.content}
                )
                current_response = intermediate_response

        # Max rounds reached — synthesize without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
        }
        return self.client.messages.create(**final_params).content[0].text
