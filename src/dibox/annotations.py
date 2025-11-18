import inspect
from typing import Annotated, Callable, TypeVar, get_args, get_origin

T = TypeVar('T')

_injected_mark = object()
_not_injected_mark = object()

Injected = Annotated[T, _injected_mark]
"""
Marker for parameters used by inject() decorator with inject_mode=InjectMode.Marked
that should be injected by the DI container.
"""

NotInjected = Annotated[T, _not_injected_mark]
"""
Marker for parameters used by inject() decorator with inject_mode=InjectMode.All
that should not be injected by the DI container.
"""


def get_injected_type(p: inspect.Parameter, inject_all: bool) -> type | None:
    if get_origin(p.annotation) == Annotated and len(annotation_args := get_args(p.annotation)) == 2:
        if annotation_args[1] == _injected_mark:
            return annotation_args[0]
        elif annotation_args[1] == _not_injected_mark:
            return None
    return p.annotation if inject_all else None


def get_injected_params(func: Callable, inject_all: bool = False) -> dict[str, type]:
    res = {}
    for p in inspect.signature(func).parameters.values():
        injected_type = get_injected_type(p, inject_all)
        if injected_type is not None:
            res[p.name] = injected_type
    return res


def remove_params_from_signature(func: Callable, params: dict[str, type]):
    s = inspect.signature(func)
    s = s.replace(parameters=[p for p in s.parameters.values() if p.name not in params])
    func.__signature__ = s  # type: ignore
