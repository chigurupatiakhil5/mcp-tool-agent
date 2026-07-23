"""Prove v5's actual goal: every agent run is fully traceable in the
database, not just visible while it's happening. Run from the project root:

    python -m scripts.show_run_history          # most recent run
    python -m scripts.show_run_history 3         # a specific run by id
"""

import json
import sys

from app.database import SessionLocal
from app.models import AgentRun


def main() -> None:
    db = SessionLocal()
    try:
        if len(sys.argv) > 1:
            run = db.query(AgentRun).filter(AgentRun.id == int(sys.argv[1])).first()
        else:
            run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()

        if run is None:
            print("No agent runs found.")
            return

        print(f"Run #{run.id}  [{run.status}]")
        print(f"Task:      {run.task}")
        print(f"Started:   {run.started_at}")
        print(f"Completed: {run.completed_at}")
        print(f"Answer:    {run.final_answer}")
        print(f"\n{len(run.tool_calls)} tool call(s):")

        for call in run.tool_calls:
            status = "OK" if call.success else "FAILED"
            print(f"\n  [{call.iteration}] {call.tool_name} - {status}")
            print(f"      args:   {json.dumps(call.arguments)}")
            print(f"      result: {json.dumps(call.result)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
