import json
from datetime import datetime, timezone

from groq import Groq

from agent.client import mcp_session, mcp_tool_to_groq_tool
from agent.config import settings
from app.database import SessionLocal
from app.models import AgentRun, ToolCall

MODEL = "llama-3.3-70b-versatile"
MAX_ITERATIONS = 8
MAX_CONSECUTIVE_FAILURES = 3

SYSTEM_PROMPT = (
    "You are an autonomous agent with access to tools for querying a "
    "database of health checks, creating support tickets, and looking up "
    "current weather. Break the user's task into steps. Call one or more "
    "tools as needed, then give a final, plain-language answer once the "
    "task is complete.\n\n"
    'Every tool result includes "success": true or false. If "success" is '
    'false, the call did not work - read its "error" message and change '
    "your approach before trying again: fix the input, try a different "
    "tool, or try different arguments. Do not call the exact same tool "
    "with the exact same arguments again after a failure - it will fail "
    "the same way every time. If you cannot complete the task after a "
    "reasonable alternative also fails, say so clearly instead of "
    "pretending it worked."
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


def _is_failure(result, tool_output: object) -> bool:
    """A call can fail two different ways: the MCP protocol layer marks it
    isError (unknown tool, arguments that fail schema validation, an
    uncaught exception inside the tool - verified in v4 that none of these
    raise a Python exception at the client, they all come back as a normal
    CallToolResult with isError=True), or the tool ran fine but reported
    its own business-logic failure (our ToolError shape from v2, e.g. "city
    not found"). Both mean this result is not usable data."""
    if result.isError:
        return True
    return isinstance(tool_output, dict) and "error" in tool_output


def _start_run_log(db, task: str):
    """Best-effort: create the agent_runs row for this task. Returns the
    AgentRun, or None if logging itself failed - the agent still proceeds
    with the actual task either way (see module docstring below on why
    logging must never be allowed to crash the task it's logging)."""
    try:
        run = AgentRun(task=task, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        print(f"[agent] WARNING: failed to log run start: {exc}")
        db.rollback()
        return None


def _log_tool_call(db, run, iteration: int, tool_name: str, arguments: dict, success: bool, result: object) -> None:
    if run is None:
        return
    try:
        db.add(
            ToolCall(
                agent_run_id=run.id,
                iteration=iteration,
                tool_name=tool_name,
                arguments=arguments,
                success=success,
                result=result if isinstance(result, dict) else {"value": result},
            )
        )
        db.commit()
    except Exception as exc:
        print(f"[agent] WARNING: failed to log tool call: {exc}")
        db.rollback()


def _finish_run_log(db, run, status: str, final_answer: str) -> None:
    if run is None:
        return
    try:
        run.status = status
        run.final_answer = final_answer
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        print(f"[agent] WARNING: failed to log run completion: {exc}")
        db.rollback()


async def run_task(task: str) -> str:
    """Runs the agent loop for a single task and returns the final answer.

    Every run and every tool call within it is logged to Postgres
    (agent_runs, tool_calls) as it happens - not batched at the end, so a
    run that never finishes (crashes, gets killed) still leaves a partial,
    genuinely useful trace of what happened before that point. Logging
    writes are wrapped defensively: a logging failure prints a warning and
    is swallowed rather than propagated, because a database hiccup while
    writing a log row should never be allowed to fail a tool call or task
    that otherwise succeeded - the log is a record of the work, not the
    work itself.
    """
    groq_client = Groq(api_key=settings.groq_api_key)
    db = SessionLocal()
    run = _start_run_log(db, task)

    try:
        async with mcp_session() as session:
            tools_result = await session.list_tools()
            groq_tools = [mcp_tool_to_groq_tool(tool) for tool in tools_result.tools]

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]

            consecutive_failures = 0
            last_error_message = None

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
                    _finish_run_log(db, run, "completed", message.content)
                    return message.content

                # Re-post the assistant's own message (including which
                # tools it decided to call) before the tool results, so the
                # model's next turn has the full record of what it already
                # decided to do.
                messages.append(message.model_dump(exclude_none=True))

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    print(f"[agent] iteration {iteration}: calling {tool_name}({tool_args})")
                    result = await session.call_tool(tool_name, tool_args)
                    tool_output = _extract_tool_output(result)
                    failed = _is_failure(result, tool_output)

                    if failed:
                        consecutive_failures += 1
                        last_error_message = (
                            tool_output.get("error")
                            if isinstance(tool_output, dict)
                            else str(tool_output)
                        )
                        print(
                            f"[agent] iteration {iteration}: FAILED "
                            f"(consecutive failures: {consecutive_failures}) -> {last_error_message}"
                        )
                    else:
                        consecutive_failures = 0
                        print(f"[agent] iteration {iteration}: result = {tool_output}")

                    _log_tool_call(db, run, iteration, tool_name, tool_args, not failed, tool_output)

                    # Explicit "success" field, not just an "error" key's
                    # presence-or-absence - a consistent, unambiguous signal
                    # the model doesn't have to infer.
                    envelope = (
                        {"success": False, "error": last_error_message}
                        if failed
                        else {"success": True, "data": tool_output}
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(envelope),
                        }
                    )

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(
                        f"[agent] stopping: {consecutive_failures} consecutive tool "
                        "failures - giving up rather than retrying indefinitely"
                    )
                    answer = (
                        "I was unable to complete this task: tool calls failed "
                        f"{consecutive_failures} times in a row. Last error: {last_error_message}"
                    )
                    _finish_run_log(db, run, "failed", answer)
                    return answer

            answer = f"Stopped after {MAX_ITERATIONS} iterations without a final answer."
            _finish_run_log(db, run, "failed", answer)
            return answer
    finally:
        db.close()
