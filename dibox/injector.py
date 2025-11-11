import inspect
from enum import Enum
from functools import update_wrapper
from typing import Callable, Type

from .annotations import get_injected_params, remove_params_from_signature
from .dibox import DIBox

global_dibox = DIBox()

class InjectMode(Enum):
    All = "all"
    Marked = "marked"

def inject(container: DIBox = global_dibox, inject_mode: InjectMode = InjectMode.Marked):
    def decorator(func):
        injected_params = get_injected_params(func, inject_mode == InjectMode.All)
        if inspect.iscoroutinefunction(func):
            wrapper = _make_async_wrapper(func, container, injected_params)
        else:
            wrapper = _make_sync_wrapper(func, container, injected_params)
        update_wrapper(wrapper, func)
        remove_params_from_signature(wrapper, injected_params)
        return wrapper
    return decorator

def inject_all(container: DIBox = global_dibox):
    return inject(container, InjectMode.All)

def _make_async_wrapper(func: Callable, container: DIBox, injected_params: dict[str, Type]):
    async def wrapper(*args, **kwds):
        dependencies = {}
        for param_name, param_type in injected_params.items():
            if param_name not in kwds:
                dependencies[param_name] = await container.provide(param_type, param_name)
        return await func(*args, **{**dependencies, **kwds})
    return wrapper


def _make_sync_wrapper(func: Callable, container: DIBox, injected_params: dict[str, Type]):
    def wrapper(*args, **kwds):
        dependencies = {}
        for param_name, param_type in injected_params.items():
            if param_name not in kwds:
                dependencies[param_name] = container.resolve(param_type, param_name)
        return func(*args, **{**dependencies, **kwds})
    return wrapper
