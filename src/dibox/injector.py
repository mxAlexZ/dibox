import inspect
from enum import Enum
from functools import update_wrapper
from typing import Callable, Type

from .annotations import get_injected_params, remove_params_from_signature
from .dibox import DIBox

global_dibox = DIBox()

class InjectMode(Enum):
    """
    Specifies the mode of dependency injection for the inject decorator:
    whether all parameters with type hints should be considered for injection,
    or only those explicitly marked.
    """
    All = "all"
    Marked = "marked"

def inject(container: DIBox = global_dibox, inject_mode: InjectMode = InjectMode.Marked):
    """
    Decorator for injecting dependencies into a function from a DI container.

    This decorator should only be used at application entry points; for example,
    at REST endpoint definitions like AWS lambda handlers or FastAPI routes.

    By default (in `InjectMode.Marked`), it injects dependencies only for
    parameters annotated with `Injected`. The decorated function's signature is
    modified to remove the injected parameters, so they don't need to be passed
    when calling it. However, they can still be passed as keyword arguments to
    override the injection.

    Usage example:
    ```python
    @inject()
    def consumer(foo: Injected[Foo]):
        ...

    # foo will be resolved automatically
    consumer()

    # But you can still override it
    consumer(foo=...)
    ```
    """
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
    """A shorthand for `inject(container, InjectMode.All)`."""
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
                dependencies[param_name] = container.get(param_type, param_name)
        return func(*args, **{**dependencies, **kwds})
    return wrapper
