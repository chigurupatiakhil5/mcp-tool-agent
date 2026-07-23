"""Give the agent a task and watch it work. Run from the project root:

    python -m scripts.run_agent_task "your task here"

If no task is given, runs a default multi-step task that exercises at
least two tools in sequence, matching v3's goal.
"""

import asyncio
import sys

from agent.planner import run_task

DEFAULT_TASK = (
    "Check the current weather in Austin. If the temperature is above 30 "
    "degrees Celsius, create a high-priority support ticket titled "
    "'Server room cooling check' with a description explaining that "
    "outdoor temperatures may stress the server room's cooling system."
)


async def main() -> None:
    task = " ".join(sys.argv[1:]) or DEFAULT_TASK

    print(f"Task: {task}\n")
    answer = await run_task(task)
    print(f"\nFinal answer: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
