from typing import Any

from .dimap import ANY_ARG, TypeQuery, WildArgName

ResolutionFrame = tuple[TypeQuery[Any], WildArgName]
ResolutionStack = list[ResolutionFrame]


def format_type(type_query: TypeQuery[Any]) -> str:
    return getattr(type_query, "__qualname__", None) or str(type_query)


def format_frame(type_query: TypeQuery[Any], name: WildArgName) -> str:
    return (
        format_type(type_query)
        if name is ANY_ARG
        else f"{name}: {format_type(type_query)}"
    )


def format_resolution_path(resolution_stack: ResolutionStack) -> str:
    requested_type, name = resolution_stack[-1]
    formatted_stack = [f"- {format_frame(requested_type, name)}  <-- failure"]
    formatted_stack += [
        f"- {format_frame(t, n)}"
        for t, n in reversed(resolution_stack[:-1])
    ]
    return "\n".join(formatted_stack)