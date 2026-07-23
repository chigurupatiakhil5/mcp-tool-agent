from typing_extensions import TypedDict

# typing_extensions.TypedDict, not typing.TypedDict: Pydantic (which FastMCP
# uses to build output schemas) requires the typing_extensions version on
# Python < 3.12 when a TypedDict is used inside a Union - the stdlib
# typing.TypedDict is missing metadata Pydantic needs in that case, and the
# failure mode is not a clear error, it's the whole server connection
# silently closing. Learned this the hard way while building this version.


class ToolError(TypedDict):
    """Shared error shape returned by any tool that can fail on bad input or
    an external dependency, instead of raising and crashing the whole call.
    Every tool that can fail declares its return type as
    Union[SuccessShape, ToolError] so FastMCP generates a schema describing
    both possibilities, and so result.structuredContent is always populated
    - the agent (v3+) can rely on structured data instead of having to
    parse text content."""

    error: str
