from typing import Any

from .dimap import ArgNameQuery, TypeQuery

ResolutionFrame = tuple[TypeQuery[Any], ArgNameQuery]
ResolutionStack = list[ResolutionFrame]


def format_type(type_query: TypeQuery[Any]) -> str:
    return (
        "None"
        if type_query is type(None)
        else getattr(type_query, "__qualname__", None) or str(type_query)
    )


def format_frame(type_query: TypeQuery[Any] | None, name: ArgNameQuery) -> str:
    return (
        format_type(type_query)
        if name is None
        else f"{name}: {format_type(type_query)}"
    )
