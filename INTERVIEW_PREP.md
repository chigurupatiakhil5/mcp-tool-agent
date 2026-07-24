# Interview Prep — MCP Tool Agent

Everything below reflects what was actually built and actually verified during this project's build, version by version — including the real bugs found and fixed, not a cleaned-up retelling.

---

## v0 — Foundation

### WHAT WE BUILT

A FastAPI service connected to PostgreSQL, fully containerized with Docker Compose. Three endpoints: `/` (status), `/health` (liveness — doesn't touch the database), `/health/db` (readiness — inserts and reads a real row every call, so calling it twice visibly increments a counter).

Files: `app/config.py` (typed settings via pydantic-settings), `app/database.py` (pooled SQLAlchemy engine + `get_db()` dependency), `app/models.py` (`HealthCheck` model), `app/main.py` (the three endpoints), `db/init.sql` (schema — the single source of truth for table structure), `docker-compose.yml`, `Dockerfile`.

This is the foundation every later version's database access builds on directly — nothing after this reimplements connection handling.

### TOOLS & TECHNOLOGIES USED

- **FastAPI** — Python web framework; decorator-based routing, automatic OpenAPI docs, first-class type hint support.
- **PostgreSQL** — relational database, chosen up front because later versions need genuinely related records (tool calls belonging to runs, foreign keys) — not a decision that could be deferred without rework.
- **SQLAlchemy** — ORM and connection pool manager. Configured explicitly: `pool_size=5, max_overflow=10, pool_pre_ping=True` — visible, tunable parameters instead of accepted defaults.
- **pydantic-settings** — typed environment variable loading. A missing required variable fails immediately at startup with a clear error, instead of `None` propagating silently until something breaks downstream.
- **Docker / Docker Compose** — containerization from the first version, not added later, specifically because the project needed to run identically on a laptop, in CI, and for anyone cloning the repo.

### WHY WE DID IT THIS WAY

- **Two separate health checks, not one.** If `/health` also queried Postgres, a slow database would make the whole app look down to anything monitoring it. Liveness and readiness are genuinely different questions.
- **Schema owned by SQL, not the ORM.** `db/init.sql` is authoritative; `app/models.py` mirrors it for querying. Letting SQLAlchemy auto-create tables would create two possible sources of truth that could drift apart.
- **Connection pooling configured explicitly.** The tradeoff of a pool this size: fine for a small app, would need tuning under real concurrent load — the point was to make that a visible, deliberate number, not a hidden default.

### INTERVIEW QUESTIONS & ANSWERS

**Q: Why two separate health endpoints instead of one?**
A: They answer different questions. `/health` proves the process is alive without touching any dependency — useful because it can't produce a false negative from a flaky database. `/health/db` specifically proves the database path works, including a real write and read, not just an open socket. Conflating them means a database hiccup makes the whole service look dead even if the web server itself is fine.

**Q: Why does the app use connection pooling instead of opening a new connection per request?**
A: Opening a database connection involves a TCP handshake, authentication, and session setup — genuinely expensive per request. A pool opens a fixed set of connections up front and hands them out, returning them after each request instead of closing them.

**Q: Why is the schema defined in raw SQL instead of letting the ORM generate it from the models?**
A: Single source of truth. If both the SQL file and the ORM could create schema, they could drift out of sync silently — a model change that forgets to update the SQL (or vice versa) becomes a real production bug. SQL owns structure; the ORM models describe how to query it.

**Q: What would happen under load if `pool_size` were too low?**
A: Requests beyond `pool_size` would use one of the `max_overflow` extra connections; beyond that, they'd queue for `pool_timeout` seconds waiting for one to free up, then fail. For this project's traffic that's a non-issue; it would be a real tuning question for anything with meaningful concurrent load.

**Q: What does `pool_pre_ping` actually protect against?**
A: A connection that's gone stale — e.g. Postgres restarted, or a firewall silently dropped an idle connection — would otherwise fail with a confusing error the first time it's reused. `pool_pre_ping` runs a cheap test query before handing a pooled connection to a request, so a dead one gets quietly replaced instead of causing a mysterious runtime failure.

---

## v1 — MCP Server Basics

### WHAT WE BUILT

A second, independent process — the MCP server — exposing one tool (`query_health_checks`) over the Model Context Protocol. `mcp_server/instance.py` holds the shared `FastMCP` object; `mcp_server/tools/db_query.py` defines the tool; `mcp_server/server.py` is the entrypoint that starts it on stdio transport. `scripts/test_mcp_tools.py` is a client that connects to it the same way any real MCP client would.

This version also corrected a default: `POSTGRES_HOST` changed from `db` (a Docker Compose service name) to `localhost`, because the MCP server runs on the host machine, not in a container.

### TOOLS & TECHNOLOGIES USED

- **Model Context Protocol** — a standardized protocol (JSON-RPC over a transport) for exposing tools to AI clients, so one server can serve many different clients without per-client integration code.
- **MCP Python SDK (`mcp` package)** — specifically `FastMCP`, the high-level, decorator-based server API (`@mcp.tool()`), and `ClientSession`/`stdio_client`/`StdioServerParameters` for the client side.
- A real correction during this version: AI-generated documentation summaries claimed classes (`MCPServer`, `Client`) that don't exist in the actually-installed package. The fix was installing the package and inspecting its real exports directly (`python -c "import mcp; print(dir(mcp))"`) rather than trusting the summary.

### WHY WE DID IT THIS WAY

- **A separate process, not a new FastAPI route.** MCP isn't HTTP — a client launches the server as a subprocess and exchanges JSON-RPC messages over its stdin/stdout. That's a fundamentally different integration shape than adding an endpoint.
- **Runs on the host, not in Docker (at this stage).** Claude Desktop needs to spawn a local process directly; it has no way to reach into a container to do that.
- **`instance.py` separated from `server.py`.** Tool modules need to import the shared `mcp` object to register themselves via decorator; the entrypoint needs to import the tool modules to trigger that registration. Putting the instance inside the entrypoint file would create a circular import the moment a second tool file existed.

### INTERVIEW QUESTIONS & ANSWERS

**Q: What is MCP, in your own words, and why does it matter?**
A: It's a standard protocol so a tool provider (an MCP server) can be built once and consumed by any compatible client — Claude Desktop, a custom agent, anything — without writing separate integration code per client-tool pair. It solves what's sometimes called the N×M integration problem.

**Q: Why does the MCP server run outside Docker while the FastAPI app runs inside it?**
A: Claude Desktop, the primary target client, launches local MCP servers as direct subprocesses on the host machine — it has no mechanism to reach into a Docker container to do that. The FastAPI app has no such constraint, so it stays containerized.

**Q: How does FastMCP generate a tool's input schema?**
A: From the function's type hints and docstring, automatically, using Pydantic under the hood. `def query_health_checks(limit: int = 5)` produces a JSON Schema describing one optional integer parameter — no hand-written schema.

**Q: What's the difference between the low-level MCP `Server` class and `FastMCP`?**
A: `FastMCP` is the ergonomic, decorator-based API used throughout this project — closer in spirit to how FastAPI itself works. The low-level `Server` class requires manually registering handlers for `list_tools`/`call_tool` and building schemas yourself; it exists for cases needing finer control than the decorator API gives.

**Q: This server currently only supports stdio transport. How would you add support for a network-based transport (e.g. for a remote client)?**
A: FastMCP supports other transports (SSE, streamable HTTP) via the same `mcp.run(transport=...)` call; the tool definitions themselves wouldn't change at all, since transport is orthogonal to what a tool does. The bigger design question would be authentication and networking, which stdio (a local subprocess) never had to consider at all.

---

## v2 — Tool Expansion

### WHAT WE BUILT

Two more tools: `create_ticket` (a write — validates input, inserts into a new `tickets` table) and `get_current_weather` (an async tool chaining two real HTTP calls to Open-Meteo — geocode a city name, then fetch its forecast). `mcp_server/types.py` added a shared `ToolError` shape used by both.

### TOOLS & TECHNOLOGIES USED

- **httpx** — async-capable HTTP client, used inside an `async def` tool since network I/O genuinely benefits from not blocking.
- **Open-Meteo** — free, no-authentication weather/geocoding API, chosen specifically so the project's setup requirements stayed at "one Groq key," not two external accounts.
- **`typing_extensions.TypedDict` + `Union`** — the mechanism for typed, structured tool outputs that can represent either success or failure.
- **`Literal` type hints** — `priority: Literal["low", "medium", "high", "urgent"]` becomes a JSON Schema `enum` automatically, pushing validation into the type system.

A genuine bug found and fixed in this version: a bare `dict` return type doesn't give FastMCP enough information to build an output schema, so `result.structuredContent` silently stays empty — the data still arrives, but only as serialized text. The deeper issue: once a return type is declared, returning a *differently-shaped* dict for an error case doesn't just skip structured output, it causes FastMCP to raise a Pydantic validation error, turning an intended clean error message into a confusing stack trace. The fix was declaring `Union[SuccessShape, ToolError]` — which itself only worked with `typing_extensions.TypedDict`, not the stdlib `typing.TypedDict`, on Python below 3.12.

### WHY WE DID IT THIS WAY

- **Write tools validate before mutating.** A bad read just returns wrong data; a bad write is a bad row in the database. `create_ticket` checks for empty title/description before touching Postgres.
- **Two chained API calls, not one.** Accepting a plain city name (not raw coordinates) makes the tool usable by an LLM without extra reasoning about geography — the tradeoff is two network calls instead of one, each independently capable of failing, each handled explicitly.
- **`Union[Success, ToolError]` instead of a bare dict.** This was the direct fix for the structured-output bug above, and it matters specifically because v3's agent needs to reliably read structured data, not text-parse.

### INTERVIEW QUESTIONS & ANSWERS

**Q: Walk me through the structured-output bug you found in this version.**
A: A tool returning a bare `dict` compiles and runs fine, but FastMCP can't build a JSON Schema for an unconstrained dict, so it can't populate `result.structuredContent` — the actual data only exists serialized as text inside a content block. Worse: once I typed the success case, returning a *different*-shaped dict for a failure case wasn't silently ignored — it caused a Pydantic validation error, since the declared type no longer matched. The real fix was declaring the return type as `Union[SuccessShape, ToolError]`, which needed `typing_extensions.TypedDict` specifically — the stdlib version doesn't carry information Pydantic needs when used inside a `Union`, on Python versions below 3.12.

**Q: Why does a write tool validate its input before writing, when a read tool doesn't need to?**
A: The cost of a bad input is different. A bad read returns wrong or empty data — annoying but harmless. A bad write persists a garbage row, and by the time anyone notices, other data may already reference it.

**Q: Why is `get_current_weather` async while `query_health_checks` isn't?**
A: `query_health_checks` runs a synchronous database call through SQLAlchemy's connection pool — no meaningful waiting to yield during. `get_current_weather` makes two real network requests, which is exactly the situation `async`/`await` is for: the process can do other work while waiting on the network instead of blocking.

**Q: How do you handle a third-party API being down or slow?**
A: Every external call has an explicit timeout (`REQUEST_TIMEOUT_SECONDS = 10`) and is wrapped to catch both `httpx.TimeoutException` and `httpx.HTTPStatusError` specifically, returning a clear `ToolError` rather than letting an unhandled exception propagate and potentially crash the tool call.

**Q: What would you change if this needed to support many more external tools?**
A: The pattern already generalizes cleanly — each tool is a self-contained file importing the shared `mcp` instance and `ToolError` type. The thing I'd revisit is the shared `httpx.AsyncClient()` — right now each call in `get_current_weather` creates its own client via a context manager; at higher volume, a shared, reused client (or connection pooling for httpx specifically) would avoid repeated connection setup overhead.

---

## v3 — Agent Client

### WHAT WE BUILT

The actual autonomous agent: `agent/client.py` (MCP connection, reusing v1's stdio pattern, plus a function translating MCP tool schemas into Groq's function-calling format), `agent/config.py` (a settings class scoped to just `GROQ_API_KEY`), and `agent/planner.py` (the agent loop itself — call Groq with the task and available tools, execute whatever tool call comes back via the real MCP connection, feed the result back into the conversation, repeat until the model returns plain text instead of another tool call).

Verified with two real runs: a task about Austin's weather (36°C) correctly triggered a second tool call to create a ticket, entirely the model's own decision; the identical task pointed at Reykjavik (10.7°C) correctly reported the temperature and created no ticket — proving the behavior was driven by real data, not a scripted sequence.

### TOOLS & TECHNOLOGIES USED

- **Groq** — inference infrastructure (not a model creator) running open-weight models on custom hardware (LPUs), exposed through an OpenAI-API-compatible interface.
- **`llama-3.3-70b-versatile`** — selected by checking Groq's live documentation at build time (not from memory), specifically because it was their stated recommendation for reliable multi-step tool use, and it's available on the free tier.
- **The agent loop pattern** — decide → act → observe → repeat, continuing until the model's response contains no tool calls.

### WHY WE DID IT THIS WAY

- **`agent/config.py` kept separate from `app/config.py`.** If `GROQ_API_KEY` were a required field on the FastAPI app's shared `Settings`, the app would refuse to start without a Groq key it never actually uses. Different components should have independent required-config surfaces.
- **A small schema-translation adapter, not two independent tool definitions.** MCP's tool schema and Groq's function-calling schema describe the same JSON Schema with different envelopes. Translating automatically means the two can never drift out of sync from a manual edit to one and not the other.
- **The model's own tool-call message is re-posted into the conversation before the tool result.** The model needs to see what it already decided, not just the outcome, or its next decision loses the "why" behind the prior step.

### INTERVIEW QUESTIONS & ANSWERS

**Q: Explain the agent loop, end to end.**
A: Send the growing conversation (system prompt, task, and every prior exchange) plus the available tools to the model. If it responds with a tool call, execute that tool for real via the MCP connection, append both the model's tool-call message and the tool's result to the conversation, and loop. If it responds with plain text instead, that's the final answer and the loop ends. Every tool call and result becomes part of what the model sees on its next turn.

**Q: Why is `GROQ_API_KEY` on a separate settings class instead of the app's shared config?**
A: Coupling would mean the FastAPI service — which never calls Groq — fails to start without a Groq key configured, purely because it shares a config class with something unrelated. Different components, different required config.

**Q: How do you translate an MCP tool's schema into something an LLM's function-calling API understands?**
A: Both ultimately describe a function's parameters as JSON Schema, just wrapped differently — MCP uses `{name, description, inputSchema}`, Groq (OpenAI-compatible) wants `{"type": "function", "function": {name, description, parameters}}`. A single adapter function does the field renaming/wrapping, so the two never need to be maintained separately.

**Q: What stops the agent from looping forever?**
A: `MAX_ITERATIONS` (8) is a hard cap on how many decide/act cycles a single task can run, independent of whether calls are succeeding or failing.

**Q: You mentioned the model sometimes calls the same tool redundantly. Isn't that a bug?**
A: It's real, observed LLM behavior, not a bug in the code — on one run, the model looked up the same city's weather twice before answering, when once would have sufficed. It's worth knowing about honestly rather than treating every imperfection as something the code should paper over; it's the kind of thing that would matter if you were optimizing for cost or latency at scale.

---

## v4 — Error Recovery

### WHAT WE BUILT

Explicit, code-level failure detection layered onto the v3 loop: `_is_failure()` unifies MCP protocol-level failures (`result.isError`) and the tool's own business-logic failures (the `ToolError` shape from v2) into one signal. Every tool result now goes back to the model as an explicit `{"success": bool, ...}` envelope. `consecutive_failures` is tracked and, if it reaches `MAX_CONSECUTIVE_FAILURES` (3), the loop stops cleanly with a clear message instead of exhausting all iterations.

Verified two ways: a genuinely failing tool call (a nonexistent city) with an explicit fallback in the task — the model correctly switched cities instead of repeating the identical failing call. And a task engineered to fail three times in a row — which revealed something real: the model made all three calls in a *single* iteration (parallel tool calling), meaning the failure cap had to be checked after each iteration's full batch of calls, not once per iteration, or it could be bypassed entirely by a burst of simultaneous failures.

### TOOLS & TECHNOLOGIES USED

No new libraries — this version is pure agent-loop logic layered on the existing MCP and Groq integrations.

### WHY WE DID IT THIS WAY

- **Retry vs. re-plan, and why the tools here need the latter.** A transient failure (a network blip) is worth retrying verbatim. Our tools' actual failure modes (a bad city name, an empty ticket title) aren't transient — repeating the identical call fails the identical way every time. The system prompt explicitly tells the model this.
- **Explicit `"success"` field, not inferred from key presence.** Relying on the model to notice an `"error"` key might or might not be there is fragile; an unambiguous boolean is not.
- **The failure cap checked per tool call, not per iteration.** This was directly validated by the parallel-tool-call discovery — an iteration-level check could have let three failures in one round through uncaught.

### INTERVIEW QUESTIONS & ANSWERS

**Q: What's the difference between retry and re-plan, and why does it matter here?**
A: Retry redoes the identical action, useful when failure was likely transient. Re-plan changes the approach — different input, different tool, or giving up cleanly — needed when the failure is deterministic given the same input. Our tools' actual failures (bad city name, empty required field) are deterministic, so the system prompt explicitly instructs the model not to repeat an identical failing call.

**Q: Why check `result.isError` explicitly instead of wrapping the tool call in try/except?**
A: Because MCP doesn't raise exceptions for bad calls — verified directly: an unknown tool name and a missing required argument both come back as a normal `CallToolResult` with `isError=True`, never a raised Python exception. Wrapping in try/except would be defending against something that structurally can't happen at that layer.

**Q: Walk me through the parallel-tool-call discovery and why it mattered.**
A: Testing the failure cap with three guaranteed-to-fail city names, I expected three iterations. Instead, the model issued all three tool calls within a single iteration — `llama-3.3-70b-versatile` supports parallel tool calling. That meant the consecutive-failure cap had to be checked after processing every tool call within an iteration's batch, not once between model turns, or three simultaneous failures could exceed the intended limit before the check ever ran.

**Q: Why have a separate consecutive-failure cap instead of just relying on `MAX_ITERATIONS`?**
A: `MAX_ITERATIONS` bounds cost and time overall, but it's a blunt instrument — it would let the agent burn through most of its budget on a task that's clearly not going to succeed. The consecutive-failure cap recognizes "this specific line of attack isn't working" and stops early with a clear explanation, rather than silently running out of iterations.

**Q: How would you distinguish a failure worth blindly retrying from one that needs re-planning?**
A: In principle, by failure type — a timeout or 5xx from an external API is plausibly transient and could warrant an automatic, code-level retry-with-backoff inside the tool itself (not implemented here, a natural next addition to `external_api.py`); a validation error or "not found" response is deterministic given the same input and needs the agent-level re-planning this version actually builds.

---

## v5 — Logging and Persistence

### WHAT WE BUILT

Two new tables, `agent_runs` (one row per task) and `tool_calls` (one row per tool invocation, foreign-keyed to its run), plus logging calls woven into `agent/planner.py` at every decision point: run start, each tool call as it happens, and run completion. `scripts/show_run_history.py` queries and prints a full run's trace, proving the data is genuinely usable, not just written and forgotten.

Verified two ways: a successful run's terminal output matched exactly what came back from a cold database query in a separate process. And the v4 three-failures-in-a-row run, queried back afterward, revealed the exact same parallel-tool-call insight (all three failures logged under iteration 1) — now permanent, queryable evidence instead of something you had to be watching the terminal to notice.

### TOOLS & TECHNOLOGIES USED

- **JSONB (PostgreSQL)** — used for the `arguments` and `result` columns instead of plain `TEXT`, specifically so the logged data stays queryable with real SQL (demonstrated with a `GROUP BY`/`FILTER` aggregate query across both tables), not just archived as an opaque blob.
- **SQLAlchemy `relationship()`** — `AgentRun.tool_calls` gives ORM-level parent-child navigation matching the actual foreign key.

### WHY WE DID IT THIS WAY

- **Logging is defensive by design.** Every logging write is wrapped in try/except with a rollback and a printed warning — a database hiccup while writing a *log* row must never be allowed to fail a tool call or task that otherwise succeeded.
- **Logged incrementally, not batched at the end.** A run that crashes or is killed partway through still leaves a partial, genuinely useful trace, rather than nothing at all.
- **Synchronous database writes inside an `async def` function** — a deliberate, acknowledged simplification for an agent handling one task at a time, not an oversight. It would need to become a real async database layer (`asyncpg` + SQLAlchemy's async engine) if this ran many concurrent tasks in one process, since a blocking write would otherwise stall the event loop for everything else.

### INTERVIEW QUESTIONS & ANSWERS

**Q: Why JSONB instead of TEXT for the arguments/result columns?**
A: JSONB stays queryable with real SQL — you can `SELECT`, filter, and aggregate into the structure directly, which I demonstrated with a `GROUP BY` query joining `agent_runs` and `tool_calls`. Storing the same data as a JSON string in a TEXT column would make it opaque to the database — readable only after pulling it out and parsing it in application code.

**Q: Why log incrementally instead of collecting everything in memory and writing it once at the end?**
A: A crashed or killed run still leaves a partial, genuinely useful trace — you can see exactly how far it got. Batching at the end means a run that never reaches "the end" leaves zero record of what happened, which defeats the actual purpose of an audit trail.

**Q: Why are all the logging writes wrapped in try/except?**
A: Because a logging failure is strictly less important than the task it's logging — if Postgres hiccups while writing a log row, that should produce a warning, not take down an otherwise-successful tool call with it. A logging system that can crash the thing it's logging is worse than no logging system.

**Q: You're doing synchronous database calls inside an async function — isn't that a mistake?**
A: It's a conscious tradeoff, not an oversight. For an agent processing one task at a time, a blocking write briefly stalling the event loop has no real consequence. It would become a genuine problem if this needed to run many agent tasks concurrently in one process, since a blocking call would then stall every other task's progress too — the correct fix at that point is an async database layer, which is a real architectural change, not something to bolt on halfway.

**Q: How would this need to change to support many concurrent agent runs?**
A: Move `app/database.py` to `asyncpg` + SQLAlchemy's async engine (`create_async_engine`/`AsyncSession`), and update every place that currently uses the sync `SessionLocal` — the MCP tools, the FastAPI app, and the agent's logging calls — to use `await` consistently. It's a coordinated change across the codebase, not a one-file fix.

---

## v6 — Infrastructure

### WHAT WE BUILT

An automated test suite split across two levels: `tests/test_tools.py` (unit tests calling MCP tool functions directly, bypassing the protocol) and `tests/test_mcp_protocol.py` (integration tests through the real MCP stdio protocol, exercising schema generation and `structuredContent` behavior that the unit tests never touch). `scripts/apply_schema.py` made schema application idempotent and reusable, replacing manual commands. `docker-compose.yml` gained an `agent` service — the same image as `app`, since the agent launches the MCP server as its own internal subprocess; there's no standalone MCP server container, because a stdio-transport server has no persistent stdin to read from without a client attached. `.github/workflows/ci.yml` runs lint, schema application, and tests against a real Postgres service container on every push, plus a separate job confirming both Docker images still build.

Two real bugs were found and fixed by actually running the containerized path rather than assuming it would work because the host version did:

1. `StdioServerParameters` defaults to a restricted environment allow-list for spawned subprocesses, not full inheritance — so the MCP server subprocess never received `POSTGRES_*`/`GROQ_*` config inside Docker. This bug existed since v3; it was invisible on the host because `app/config.py` falls back to reading the `.env` file directly from disk regardless of inherited environment variables, and there's no such file inside a container.
2. `restart: "no"` on the `agent` service did not keep it out of a plain `docker compose up` — that field only governs behavior *after* a container exits, not whether `up` starts it. The correct mechanism, verified afterward, is Docker Compose `profiles`.

### TOOLS & TECHNOLOGIES USED

- **pytest / pytest-asyncio** — `asyncio_mode = auto` in `pytest.ini`, so async test functions don't need per-test `@pytest.mark.asyncio` decorators.
- **GitHub Actions service containers** — a real, ephemeral Postgres for the test job, matching production far more closely than a mocked database would.
- **Docker Compose `profiles`** — the actual mechanism for excluding a service from a plain `up`.

### WHY WE DID IT THIS WAY

- **Two test levels because they catch genuinely different bugs.** The unit tests would never have caught the v2 `structuredContent` issue, since that only exists at the protocol layer; the integration tests would be slow and awkward as the primary way to test plain validation logic.
- **No standalone MCP server container.** The architecture only ever supported the MCP server as a subprocess of whichever client launched it — containerizing the agent containerizes the MCP server along with it, for that context, without inventing a new deployment shape that doesn't match how stdio transport actually works.
- **CI deliberately doesn't test the Groq-powered agent loop.** That would require a `GROQ_API_KEY` as a repository secret and real network calls to an LLM on every single push — a genuine cost and flakiness tradeoff the project doesn't take on. The chosen test suite covers everything the tools themselves promise, independent of any particular LLM's specific tool-calling decisions.
- **Both bugs were found by testing under the real target conditions**, not by code review: the environment bug only appeared once actually run inside Docker; the profile issue only appeared once `docker compose ps` was actually checked after `up`. Before ever pushing to GitHub, the CI job's exact conditions were simulated locally — `.env` file physically removed, a completely fresh throwaway Postgres container, only real environment variables set — and the full suite passed under those conditions specifically.

### INTERVIEW QUESTIONS & ANSWERS

**Q: Walk me through the environment-inheritance bug you found in Docker — root cause and fix.**
A: `StdioServerParameters`, used to launch the MCP server as a subprocess, defaults its `env` parameter to `None`, which the SDK documents as giving the child process a restricted allow-list of environment variables, not full inheritance — a sensible default for launching an arbitrary third-party server, wrong for launching our own trusted code. This existed since v3 without being noticed because, on the host, `app/config.py` (via pydantic-settings) falls back to reading the `.env` file directly from disk regardless of what environment variables were actually inherited — and the subprocess's working directory happened to match the project root, so the file was always found. Inside a Docker container there is no `.env` file at all, only injected environment variables — which immediately exposed the gap as a Pydantic validation error. Fixed with `env=dict(os.environ)`, explicitly forwarding the full parent environment.

**Q: Why doesn't `restart: "no"` keep a service out of `docker compose up`? What does?**
A: `restart` policies control what Docker does after a container exits — restart it, or leave it stopped — they say nothing about whether `up` starts the container in the first place; `up` starts every defined service by default regardless of its restart policy. The actual mechanism for exclusion is Compose `profiles` — assigning a service to a named profile excludes it from a bare `up` unless that profile is activated or the service is targeted directly by name (e.g. `docker compose run --rm agent`, which still works even with a profile assigned).

**Q: Why split unit tests and integration tests into separate approaches instead of one uniform test style?**
A: They test different layers and catch different bugs. Calling `create_ticket()` directly as a Python function tests validation and database logic fast, with no protocol overhead. Going through the real MCP server over stdio is the only way to exercise schema generation and `structuredContent` behavior — v2's entire structured-output bug lived exclusively at that layer and would be invisible to a pure unit test.

**Q: Why doesn't CI test the agent's actual LLM-driven behavior?**
A: That would require a `GROQ_API_KEY` as a CI secret and real network calls to Groq on every push — a real cost and reliability tradeoff (API rate limits, occasional latency, a third-party dependency for the pipeline to go green). The test suite instead covers everything the tools themselves promise — which is testable deterministically — independent of any particular LLM's specific decisions.

**Q: How did you validate the CI workflow would pass before ever pushing to GitHub?**
A: `act` (a local GitHub Actions runner) wasn't installed and I didn't want to install new tooling unprompted, so instead I reproduced CI's exact conditions by hand: physically moved the `.env` file out of the way, spun up a completely fresh, empty Postgres container matching CI's exact image and credentials, exported only the plain environment variables CI's workflow file declares, and ran the identical commands (`ruff check .`, `python -m scripts.apply_schema`, `pytest -v`) against that. Everything passed under those conditions specifically, which is meaningfully stronger evidence than "it works on my machine."

---

## v7 — Polish

### WHAT WE BUILT

A complete README with a Mermaid architecture diagram (renders natively on GitHub), a full project structure with one-line descriptions, a complete environment variable table, and real, verified example agent runs pulled from earlier in this project's own build — not invented for the README. A real linter pass with `ruff`: 8 genuinely fixable issues corrected (nested context managers combined, `Union`/`Optional` modernized to `|` syntax, import formatting), and 2 flagged issues deliberately kept as-is with explained `# noqa` comments, because they're false positives specific to this codebase's actual design (a defensively broad `except Exception` in logging helpers whose entire purpose is catching anything; `Depends(...)` as a FastAPI route's default argument, which is the correct, idiomatic dependency-injection pattern, not a real bug). This document.

### TOOLS & TECHNOLOGIES USED

- **ruff** — fast Python linter, run for real (`ruff check .`) rather than "cleanup" meaning an unstructured manual read-through.
- **Mermaid** — diagram-as-code; GitHub renders fenced ` ```mermaid ` blocks natively in Markdown, no external image asset needed.

### WHY WE DID IT THIS WAY

- **A real linter, not just eyeballing the code.** "Code cleanup" as a checkbox is nearly meaningless; running an actual tool and reading its real output turned up genuine, mechanical issues that had accumulated silently across seven versions of moving quickly.
- **Distinguishing real issues from false positives, and documenting the distinction.** Silently suppressing a linter warning with a bare `# noqa` just hides information from the next reader; explaining *why* a flagged pattern is intentional here (not universally correct, but correct in this specific context) is more honest and more useful.
- **Documented example runs are real, not invented.** Every example in the README's "Example agent runs" section is copied from an actual verified run earlier in this project's build — using fabricated-but-plausible output would misrepresent what the system actually does.

### INTERVIEW QUESTIONS & ANSWERS

**Q: How did you approach "code cleanup" concretely, rather than just reading through files?**
A: Ran `ruff check .` — a real static analysis tool — over the whole codebase, rather than relying on a manual pass to catch style issues consistently. It found 16 genuine issues; I fixed the 8 that were unambiguous improvements (redundant nested context managers, outdated typing syntax) and re-ran the full test suite afterward specifically to confirm the purely cosmetic changes hadn't broken anything.

**Q: Why keep the broad `except Exception` in the logging helpers instead of narrowing it, like the linter suggested?**
A: Narrowing it would mean picking specific exception types to catch — but the actual design intent is "catch any possible failure while writing a log row, because a logging failure must never be allowed to crash the task it's logging." A narrower catch would silently stop achieving that goal the first time an unanticipated exception type came from the database driver. I kept the broad catch and added a `# noqa` with an explanation instead of narrowing it just to satisfy the linter.

**Q: Why is `Depends(get_db)` in a function's default argument not a bug, despite what a generic linter flags?**
A: That specific pattern — a mutable-looking function call as a default argument — is a real anti-pattern in general Python, which is why the linter flags it. But it's also the literal, documented, idiomatic way FastAPI's dependency injection system works: FastAPI inspects the default value at request time and calls `get_db()` itself, per-request, rather than the default being evaluated once at function definition time the way a normal Python default would be. The generic rule doesn't know about FastAPI's special handling.

**Q: What makes a good architecture diagram for a project like this?**
A: Showing the actual decision points, not just boxes and arrows — in this diagram, that meant making clear there's no standalone MCP server box, because that would misrepresent the real architecture (the MCP server only ever exists as a subprocess of whichever client launched it). A diagram that's technically accurate but glosses over the interesting design decision is less useful than one that reflects what was actually learned building the thing.

**Q: What would you still want to add if you had one more week?**
A: Three things, roughly in priority order: an async database layer so the agent could handle concurrent tasks without blocking (flagged explicitly as a deliberate simplification in v5); a code-level retry-with-backoff inside `external_api.py` specifically for transient network failures, complementing (not replacing) the agent-level re-planning from v4; and CI coverage of the actual agent loop, gated behind a `GROQ_API_KEY` repository secret, run on a schedule rather than every push to control cost.

---

## FULL SYSTEM OVERVIEW

### How the entire system works, end to end

A user (or Claude Desktop, or the agent script) wants something done — check a data point, create a ticket, look something up externally. The MCP server, a small standalone process, exposes exactly three capabilities over the Model Context Protocol: read from a database table, write a new ticket to it, and call a real external weather API. It doesn't decide anything — it just describes what it can do and does it when asked.

The interesting part is who does the asking. Claude Desktop can launch the MCP server directly and call its tools within a conversation. Separately, this project's own agent — powered by Groq's free-tier LLaMA 3.3, not Claude — launches the *same* MCP server as its own subprocess, and runs a loop: describe the task to the model, let it decide which tool (if any) to call, actually execute that tool through the real MCP connection, show the model the result, and repeat until the model has a final answer instead of another tool call. If a tool call fails, the agent doesn't crash — it's told explicitly and expected to change its approach rather than repeat the identical failing call, bounded by a hard cap so it can never loop forever on a lost cause.

Every run and every tool call within it — what was attempted, what came back, whether it succeeded — is written to PostgreSQL as it happens, not after the fact, so a run's full history survives even if the process is killed mid-task. A separate, always-running FastAPI service shares the same database purely for its own liveness/readiness checks; it has no other role in the agent's behavior. The whole system — database, web service, and the agent (MCP server included, launched internally) — can be brought up with Docker Compose, and an automated test suite covering both the tools' internal logic and the real MCP protocol runs on every push via GitHub Actions.

### Complete final folder structure

```
mcp-tool-agent/
├── README.md                          project overview, architecture diagram, setup, examples
├── INTERVIEW_PREP.md                  this file
├── .env.example                       template for required environment variables
├── .gitignore                         excludes .venv, .env, __pycache__, etc.
├── .dockerignore                      keeps the Docker build context lean
├── pytest.ini                         asyncio_mode = auto
├── requirements.txt                   all Python dependencies, version-pinned
├── docker-compose.yml                 db, app, and agent (profile-gated) services
├── Dockerfile                         shared image for the app and agent services
├── .github/
│   └── workflows/
│       └── ci.yml                     lint, apply schema, test, and docker-build on every push
├── db/
│   └── init.sql                       schema: health_check, tickets, agent_runs, tool_calls
├── app/                                FastAPI service and shared database layer
│   ├── __init__.py
│   ├── config.py                        typed Postgres settings
│   ├── database.py                      pooled SQLAlchemy engine, get_db() dependency
│   ├── models.py                        HealthCheck, Ticket, AgentRun, ToolCall
│   └── main.py                          /, /health, /health/db endpoints
├── mcp_server/                         the MCP server
│   ├── __init__.py
│   ├── instance.py                      shared FastMCP instance
│   ├── types.py                         shared ToolError shape
│   ├── server.py                        entrypoint (stdio transport)
│   └── tools/
│       ├── __init__.py
│       ├── db_query.py                    query_health_checks (read)
│       ├── ticket_create.py               create_ticket (write)
│       └── external_api.py                get_current_weather (external API, async)
├── agent/                              the autonomous agent
│   ├── __init__.py
│   ├── client.py                        MCP connection + MCP-to-Groq schema adapter
│   ├── config.py                        settings scoped to GROQ_API_KEY only
│   └── planner.py                       the agent loop: decide, act, observe, repeat
├── scripts/                            runnable entrypoints
│   ├── __init__.py
│   ├── run_agent_task.py                give the agent a task, watch it work
│   ├── show_run_history.py              query a run's full trace from Postgres
│   ├── apply_schema.py                  idempotent schema application
│   └── test_mcp_tools.py                manual smoke test of all 3 tools
└── tests/                              automated test suite
    ├── conftest.py                       shared db fixture
    ├── test_tools.py                     unit: tool functions called directly
    └── test_mcp_protocol.py              integration: through the real MCP protocol
```

### Every tool used across the entire project

- **FastAPI** — web framework for the always-on service; liveness/readiness endpoints.
- **PostgreSQL** — the single database backing tool data, ticket records, and the full agent audit trail.
- **SQLAlchemy** — ORM, connection pooling, and (via JSONB columns) queryable structured log storage.
- **pydantic-settings** — typed, fail-fast environment variable loading, used by two independent settings classes (`app/config.py`, `agent/config.py`) deliberately kept separate.
- **Docker / Docker Compose** — containerization for the database, the FastAPI app, and (via Compose profiles) an on-demand, fully containerized agent.
- **GitHub Actions** — CI: lint (ruff), schema application, automated tests against a real Postgres service container, and a Docker build check, on every push.
- **Model Context Protocol / MCP Python SDK (`mcp`)** — the protocol and library the tool server and every client (Claude Desktop, the agent, the test scripts) speak to each other over.
- **httpx** — async HTTP client for the real external weather API calls.
- **Open-Meteo** — free, no-auth weather and geocoding API, the project's one real third-party data source.
- **Groq** — inference infrastructure serving the LLaMA model the agent uses to reason and decide.
- **`llama-3.3-70b-versatile`** — the specific model, chosen for confirmed reliable multi-step tool-calling support.
- **pytest / pytest-asyncio** — the automated test suite, covering both direct tool-function calls and the real MCP protocol.
- **ruff** — static analysis / linting, run for real as part of both local cleanup and CI.

---

## RESUME ADDITIONS

### Bullet points

- Designed and built a custom MCP (Model Context Protocol) server exposing database, ticketing, and external-API tools to both Claude Desktop and a self-built autonomous agent, using the official Anthropic MCP SDK
- Built an autonomous agent client powered by Groq's LLaMA 3.3 that plans and executes multi-step tasks by chaining tool calls, with explicit failure detection and bounded re-planning so a failed tool call never halts execution
- Implemented full observability for agent behavior: every decision and tool call — inputs, outputs, and success/failure — persisted to PostgreSQL in real time, queryable end-to-end after the fact
- Found and fixed a subprocess environment-inheritance bug and a Docker Compose service-startup misconfiguration by containerizing and testing the full system end-to-end, rather than assuming host-verified behavior would carry over
- Shipped with a full automated test suite (unit + real-protocol integration tests) and a GitHub Actions CI pipeline (lint, test, Docker build) validated against production-like conditions before the first push

### Tech stack line

**Python · FastAPI · Anthropic MCP SDK · Model Context Protocol · Groq API (LLaMA 3.3) · PostgreSQL · SQLAlchemy · Docker & Docker Compose · GitHub Actions · pytest**

---

## MASTER INTERVIEW QUESTIONS

1. **What does this project do, in one or two sentences?**
   A custom MCP server exposes database, ticketing, and external-API tools to Claude Desktop and to a self-built agent powered by Groq's LLaMA 3.3; the agent plans multi-step tasks, calls tools autonomously, recovers from failures instead of crashing, and logs everything to PostgreSQL.

2. **Why build a custom MCP server instead of just using an off-the-shelf one?**
   The point was learning to build the provider side of the protocol, not just consume it — most engineers' MCP experience is limited to using servers someone else wrote (GitHub, Slack, etc.). Building one from scratch means understanding tool schema generation, transport mechanics, and how a server serves genuinely different clients (Claude Desktop and a custom agent) without per-client code.

3. **Why Groq/LLaMA instead of the Claude API for the agent's own reasoning, when the tool server itself uses the Anthropic MCP SDK?**
   Two separate concerns: MCP standardizes tool *access*, and says nothing about which LLM decides *when* to use them. Using Groq specifically (free tier, no cost) for the agent's own decision-making, while still using Anthropic's MCP SDK to build the server, demonstrates that MCP tools aren't locked to any one model provider.

4. **Walk me through what happens when the agent is given a task.**
   The agent connects to the MCP server (launching it as a subprocess), fetches its available tools, and sends the task plus those tools to Groq. Groq either returns a tool call or a final answer. If a tool call, the agent executes it for real via MCP, logs it to Postgres, and feeds the result back into the conversation before asking Groq again. This repeats — bounded by a max-iteration cap and a consecutive-failure cap — until a final answer arrives.

5. **What was the hardest bug in this project, and how did you find it?**
   A subprocess environment-inheritance bug: `StdioServerParameters` doesn't fully inherit the parent process's environment by default, so when the agent (correctly configured inside Docker) spawned the MCP server as its own subprocess, that child never received the database credentials. It had existed since the agent was first built, invisible because the host environment has a `.env` file the config system falls back to reading directly, regardless of what's actually inherited — Docker has no such file. Found by actually running the containerized agent rather than assuming Docker would behave like the host.

6. **How does the agent avoid infinite loops?**
   Two independent caps: `MAX_ITERATIONS` bounds the whole task regardless of outcome; `MAX_CONSECUTIVE_FAILURES` stops early specifically when tool calls keep failing, checked after every individual tool call rather than once per model turn — necessary because the model can issue multiple tool calls in a single turn.

7. **How is a tool call's success or failure determined, and why does that design matter?**
   Two independent signals are unified into one check: the MCP protocol's own `isError` flag (unknown tool, invalid arguments, an uncaught exception inside the tool) and the tool's own reported business-logic failure (a `{"error": ...}` shape a tool returns deliberately, like "city not found"). Both get folded into a single, explicit `{"success": bool, ...}` envelope sent back to the model, so the model never has to infer failure from ambiguous signals.

8. **Why does the agent log to the database incrementally instead of all at once at the end?**
   So a run that crashes or is interrupted partway through still leaves a partial, genuinely useful trace, instead of leaving no record at all — which would defeat the actual purpose of an audit trail.

9. **What tradeoff did you make with synchronous database calls inside an async agent loop?**
   The database writes (including logging) use the same synchronous SQLAlchemy session as the rest of the project, even though the agent loop itself is `async`. For a single task running at a time, that's harmless — it would become a real problem under concurrent load, where a blocking write would stall every other in-flight task, and the fix would be a genuine architectural change to an async database layer, not a quick patch.

10. **Why does the MCP server run differently depending on who's using it — sometimes on the host, sometimes in Docker?**
    Claude Desktop can only launch local MCP servers as direct subprocesses on the host machine, which containers can't satisfy. Everything else (the agent, CI, a fresh clone) doesn't share that constraint, so the same codebase runs fully containerized for those cases — same image, different startup command, no separate "MCP server image" because a stdio server has no persistent stdin without a client attached to it directly.

11. **What's the difference between your unit tests and your integration tests, concretely?**
    Unit tests call tool functions (`create_ticket`, `query_health_checks`) directly as plain Python, bypassing MCP entirely — fast, and focused on validation and database logic. Integration tests spin up the real MCP server over stdio and call tools through `ClientSession`, which is the only place schema generation and `structuredContent` behavior are actually exercised.

12. **Why doesn't your CI test the agent's actual LLM behavior?**
    That would require a Groq API key as a CI secret and real network calls to an LLM on every push — a real cost and flakiness tradeoff. The chosen scope tests everything the tools themselves promise deterministically, independent of any specific model's tool-calling decisions.

13. **How confident are you that your GitHub Actions workflow will pass, given you hadn't pushed to GitHub yet when you wrote it?**
    Fairly confident, because I simulated its exact conditions locally rather than just reading the YAML: physically removed the `.env` file, used a completely fresh Postgres container matching CI's image and credentials, exported only the plain environment variables the workflow declares, and ran the identical commands. Everything passed under those specific conditions.

14. **What would you do differently if you were rebuilding this from scratch?**
    Type tool return values from the start (`Union[Success, ToolError]`) instead of discovering the bare-`dict` structured-output gap in v2 — now that the pattern is understood, there's no reason not to apply it immediately rather than iteratively. I'd also forward the full subprocess environment (`env=dict(os.environ)`) from the first version that spawns a subprocess, rather than only catching the gap once Docker exposed it.

15. **What's the single most interesting thing you learned building this?**
    That "it worked on my machine" can be true for reasons that have nothing to do with correctness — the environment-inheritance bug worked on the host purely because of an incidental fallback path (reading `.env` directly), not because the underlying code was right. Containerizing didn't introduce a new bug; it removed the accidental safety net that had been hiding a real one since v3.

### The 5 hardest follow-ups, and how to answer them

**"If MCP already lets Claude Desktop use your tools, why bother building your own agent at all — what does it prove that Claude Desktop calling your tools wouldn't?"**
> Claude Desktop calling the tools proves the MCP server works. It doesn't demonstrate the harder half of the project: building the *client* side of an agentic loop — planning, multi-step execution, failure recovery, persistence — from scratch, on top of a model I don't control the integration for. That's the part that generalizes to "I can build an agent," not just "I can expose tools."

**"Your consecutive-failure cap resets to zero on any success within a batch of parallel tool calls, even if other calls in that same batch failed. Is that the right behavior?"**
> It's a deliberate choice, not an oversight: the cap is meant to catch "this line of attack fundamentally isn't working," and at least one success in a round is real evidence of progress. The edge case is real — two failures followed by one success in the same batch resets the counter to zero even though two things just failed — but the tradeoff favors not prematurely giving up on a task that's mostly succeeding. A stricter design would track failures and successes independently rather than net them against each other.

**"Your tools call a live third-party API (Open-Meteo) directly in your integration tests. What happens to your CI when that API has an outage?**
> The build goes red for a reason unrelated to a real code regression, which is a genuine, acknowledged tradeoff — I chose it over the added complexity of mocking httpx for a small project, but at larger scale I'd introduce a mocked or recorded-response layer (e.g. `respx` for httpx) specifically for CI, while keeping a real-network smoke test as a separate, non-blocking check.

**"You said logging failures should never crash the task. But what if the *task itself* depends on that log — for example, an audit requirement where an unlogged action is a compliance problem?"**
> Then the failure-handling policy would need to flip for that specific write — an audit-critical log needs to block on success (or use a transactional outbox pattern to guarantee eventual delivery), while a purely observational log like this project's can stay best-effort. The current design is correct for what this project's logging is actually for — visibility, not compliance — and I'd explicitly call out that distinction before assuming the same defensive pattern applies everywhere.

**"Your agent's system prompt tells the model not to repeat an identical failing call. What actually stops it from doing so anyway, given LLMs don't reliably follow instructions?"**
> Strictly, nothing at the code level enforces it — the instruction is a strong nudge, not a guarantee, and I verified compliance empirically (the Zzyzxville→Paris run) rather than assuming the prompt alone was sufficient. If I needed a hard guarantee rather than a strong tendency, I'd add code-level detection of a repeated identical `(tool_name, arguments)` pair and short-circuit it directly, rather than relying on the model to honor the instruction every time.
