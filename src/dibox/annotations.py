import inspect
from typing import Annotated, Any, Callable, TypeVar, get_args, get_origin

T = TypeVar("T")

_injected_mark = object()

Injected = Annotated[T, _injected_mark]
"""
Marker for parameters that should be injected by DIBox decorators.

Only parameters annotated as ``Injected[T]`` are resolved from the container.
"""

def get_injected_type(p: inspect.Parameter) -> type[Any] | None:
    if (
        get_origin(p.annotation) == Annotated
        and len(annotation_args := get_args(p.annotation)) >= 2
        and annotation_args[1] == _injected_mark
    ):
        return annotation_args[0]  # type: ignore[no-any-return]
    return None


def get_injected_params(func: Callable[..., Any]) -> dict[str, type[Any]]:
    res: dict[str, type[Any]] = {}
    for p in inspect.signature(func).parameters.values():
        injected_type = get_injected_type(p)
        if injected_type is not None:
            res[p.name] = injected_type
    return res


def remove_params_from_signature(func: Callable[..., Any], params: dict[str, type[Any]]) -> None:
    s = inspect.signature(func)
    s = s.replace(parameters=[p for p in s.parameters.values() if p.name not in params])
    setattr(func, "__signature__", s)
