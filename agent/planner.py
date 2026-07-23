import json

from groq import Groq

from agent.client import mcp_session, mcp_tool_to_groq_tool
from agent.config import settings

MODEL = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 8

SYSTEM_PROMPT = (
    "You are an autonomous agent with access to tools for querying a "
    "database of health checks, creating support tickets, and looking up "
    "current weather. Break the user's task into steps. Call one or more "
    "tools as needed, then give a final, plain-language answer once the "
    "task is complete. If a tool result contains an 'error' field, that "
    "means the tool call did not succeed - explain the problem or try a "
    "different approach rather than pretending it worked."
)


def _extract_tool_output(result) -> object:
    """MCP tool results can carry structured data (result.structuredContent)
    or, if a tool has no output schema, plain text (result.content). Our
    tools (mcp_server/tools/) all declare typed return values, so
    structuredContent is populated - see v2 for why that isn't automatic.
    This unwraps the {"result": ...} envelope FastMCP adds when a tool's
    return type isn't already a single JSON object at the top level."""
    if result.structuredContent is not None:
        if "result" in result.structuredContent:
            return result.structuredContent["result"]
        return result.structuredContent

    text_parts = [block.text for block in result.content if hasattr(block, "text")]
    return {"content": "\n".join(text_parts)}


async def run_task(task: str) -> str:
    """Runs the agent loop for a single task and returns the final answer.
    Prints each step so you can watch the agent's decisions as they happen -
    this isn't a logging system (that's v5), just visibility for now."""
    groq_client = Groq(api_key=settings.groq_api_key)

    async with mcp_session() as session:
        tools_result = await session.list_tools()
        groq_tools = [mcp_tool_to_groq_tool(tool) for tool in tools_result.tools]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]

        for iteration in range(1, MAX_ITERATIONS + 1):
            response = groq_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=groq_tools,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                print(f"[agent] iteration {iteration}: final answer")
                return message.content

            # Re-post the assistant's own message (including which tools it
            # decided to call) before the tool results, so the model's next
            # turn has the full record of what it already decided to do.
            messages.append(message.model_dump(exclude_none=True))

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"[agent] iteration {iteration}: calling {tool_name}({tool_args})")
                result = await session.call_tool(tool_name, tool_args)
                tool_output = _extract_tool_output(result)
                print(f"[agent] iteration {iteration}: result = {tool_output}")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_output),
                    }
                )

        return f"Stopped after {MAX_ITERATIONS} iterations without a final answer."
